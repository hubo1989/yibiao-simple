"""文档处理相关API路由"""

import uuid
from typing import Annotated, Dict

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, status
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.schemas import (
    FileUploadResponse,
    AnalysisRequest,
    AnalysisType,
    WordExportRequest,
    ProjectFileUploadResponse,
    ProjectAnalysisRequest,
    MaterialParseResponse,
    MaterialImageInfo,
)
from ..models.user import User
from ..models.project import Project, project_members
from ..models.material import ChapterMaterialBinding
from ..db.database import get_db
from ..services.file_service import FileService
from ..services.material_service import render_content_with_material_bindings
from ..services.openai_service import OpenAIService
from ..services.prompt_service import PromptService
from ..utils.sse import sse_response
from ..auth.dependencies import require_editor
from ..config import settings

import json
import os
import io
import re
import docx
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from urllib.parse import quote

router = APIRouter(prefix="/api/document", tags=["文档处理"])


def set_run_font_simsun(run: docx.text.run.Run) -> None:
    """统一将 run 字体设置为宋体（包含 EastAsia 字体设置）"""
    run.font.name = "宋体"
    r = run._element.rPr
    if r is not None and r.rFonts is not None:
        r.rFonts.set(qn("w:eastAsia"), "宋体")


def set_paragraph_font_simsun(paragraph: docx.text.paragraph.Paragraph) -> None:
    """将段落内所有 runs 字体设置为宋体"""
    for run in paragraph.runs:
        set_run_font_simsun(run)


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: Annotated[User, Depends(require_editor)] = None,
):
    """上传文档文件并提取文本内容"""
    try:
        # 检查文件类型（Content-Type + magic bytes 双重校验）
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]

        if file.content_type not in allowed_types:
            return FileUploadResponse(
                success=False, message="不支持的文件类型，请上传PDF或Word文档"
            )

        # Magic bytes 校验：防止伪造 Content-Type
        header = await file.read(8)
        await file.seek(0)
        is_pdf = header[:5] == b"%PDF-"
        is_docx = header[:4] == b"PK\x03\x04"  # docx 本质是 ZIP
        if not (is_pdf or is_docx):
            return FileUploadResponse(
                success=False, message="文件内容与类型不匹配，请上传有效的PDF或Word文档"
            )

        # 处理文件并提取文本
        file_content = await FileService.process_uploaded_file(file)

        return FileUploadResponse(
            success=True,
            message=f"文件 {file.filename} 上传成功",
            file_content=file_content,
        )

    except Exception as e:
        return FileUploadResponse(success=False, message=f"文件处理失败: {str(e)}")


@router.post("/analyze-stream")
async def analyze_document_stream(
    request: AnalysisRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: AsyncSession = Depends(get_db),
):
    """流式分析文档内容"""
    try:
        # 创建OpenAI服务实例，从数据库加载配置
        openai_service = OpenAIService(db=db)
        if request.provider_config_id:
            configured = await openai_service.use_config_by_id(request.provider_config_id)
            if not configured:
                raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
        else:
            await openai_service._ensure_initialized()

        if not openai_service.api_key:
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        # 如果前端传了模型名称，覆盖默认模型
        if request.model_name:
            openai_service.set_model(request.model_name)

        async def generate():
            # 使用 PromptService 获取提示词（无项目上下文，使用全局/内置）
            prompt_service = PromptService(db)
            scene_key = {
                AnalysisType.OVERVIEW: "doc_analysis_overview",
                AnalysisType.REQUIREMENTS: "doc_analysis_requirements",
                AnalysisType.MATERIAL_REQUIREMENTS: "doc_analysis_requirements",
            }[request.analysis_type]
            prompt, _ = await prompt_service.get_prompt(scene_key)
            system_prompt, user_template = PromptService.split_prompt(prompt)
            user_prompt = prompt_service.render_prompt(
                user_template, {"file_content": request.file_content}
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # 流式返回分析结果
            async for chunk in openai_service.stream_chat_completion(
                messages, temperature=0.3
            ):
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

            # 发送结束信号
            yield "data: [DONE]\n\n"

        return sse_response(generate())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档分析失败: {e}") from e


@router.post("/export-word")
async def export_word(
    request: WordExportRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """根据目录数据导出Word文档"""
    try:
        doc = docx.Document()

        # 统一设置文档的基础字体为宋体，取消普通段落默认加粗
        try:
            styles = doc.styles
            base_styles = ["Normal", "Heading 1", "Heading 2", "Heading 3", "Title"]
            for style_name in base_styles:
                if style_name in styles:
                    style = styles[style_name]
                    font = style.font
                    font.name = "宋体"
                    # 设置中文字体
                    if style._element.rPr is None:
                        style._element._add_rPr()
                    rpr = style._element.rPr
                    rpr.rFonts.set(qn("w:eastAsia"), "宋体")
                    if style_name == "Normal":
                        font.bold = False
        except Exception:
            # 字体设置失败不影响文档生成，忽略
            pass

        # AI 生成声明
        p = doc.add_paragraph()
        run = p.add_run("内容由AI生成")
        run.italic = True
        run.font.size = Pt(9)
        set_run_font_simsun(run)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 文档标题
        title = request.project_name or "投标技术文件"
        title_p = doc.add_paragraph()
        title_run = title_p.add_run(title)
        title_run.bold = True
        title_run.font.size = Pt(16)
        set_run_font_simsun(title_run)
        title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 项目概述
        if request.project_overview:
            heading = doc.add_heading("项目概述", level=1)
            heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
            set_paragraph_font_simsun(heading)
            overview_p = doc.add_paragraph(request.project_overview)
            set_paragraph_font_simsun(overview_p)
            overview_p_format = overview_p.paragraph_format
            overview_p_format.space_after = Pt(12)

        # 构建图片映射表：{ "[图片N]": "绝对路径" }
        # 安全校验：防止路径穿越（../）逃逸 upload_dir
        image_map: Dict[str, str] = {}
        if request.images:
            canonical_upload_dir = os.path.realpath(settings.upload_dir)
            for marker, rel_path in request.images.items():
                # 拒绝绝对路径
                if os.path.isabs(rel_path):
                    continue
                abs_path = os.path.realpath(os.path.join(settings.upload_dir, rel_path))
                # 确保路径在 upload_dir 内
                if not abs_path.startswith(canonical_upload_dir + os.sep) and abs_path != canonical_upload_dir:
                    continue
                if os.path.exists(abs_path):
                    image_map[marker] = abs_path

        # 图片标记检测正则
        img_marker_pattern = re.compile(r'(\[图片\d+\])')

        def _insert_image_to_doc(image_path: str) -> None:
            """在文档中插入一张图片，自动限制最大宽度为 6 英寸"""
            try:
                doc.add_picture(image_path, width=Inches(6))
                # 图片居中
                last_paragraph = doc.paragraphs[-1]
                last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception:
                pass

        # 简单的 Markdown 段落解析：支持标题、列表、表格和基础加粗/斜体
        def add_markdown_runs(para: docx.text.paragraph.Paragraph, text: str) -> None:
            """在指定段落中追加 markdown 文本的 runs"""
            pattern = r"(\*\*.*?\*\*|\*.*?\*|`.*?`)"
            parts = re.split(pattern, text)
            for part in parts:
                if not part:
                    continue
                run = para.add_run()
                # 加粗
                if part.startswith("**") and part.endswith("**") and len(part) > 4:
                    run.text = part[2:-2]
                    run.bold = True
                # 斜体
                elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                    run.text = part[1:-1]
                    run.italic = True
                # 行内代码：这里只去掉反引号
                elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                    run.text = part[1:-1]
                else:
                    run.text = part
                # 确保字体为宋体
                set_run_font_simsun(run)

        def add_markdown_paragraph(text: str) -> None:
            """将一段 Markdown 文本解析为一个普通段落，保留加粗/斜体效果；遇到 [图片N] 标记则插入真实图片"""
            if not image_map:
                # 无图片映射，走原逻辑
                para = doc.add_paragraph()
                add_markdown_runs(para, text)
                para.paragraph_format.space_after = Pt(6)
                return

            # 按 [图片N] 标记切分文本
            segments = img_marker_pattern.split(text)
            for segment in segments:
                if not segment:
                    continue
                if img_marker_pattern.fullmatch(segment):
                    # 这是一个图片标记
                    if segment in image_map:
                        _insert_image_to_doc(image_map[segment])
                    else:
                        # 没有对应图片文件，保留标记文本
                        para = doc.add_paragraph()
                        run = para.add_run(segment)
                        set_run_font_simsun(run)
                        para.paragraph_format.space_after = Pt(6)
                else:
                    # 普通文本段落
                    para = doc.add_paragraph()
                    add_markdown_runs(para, segment)
                    para.paragraph_format.space_after = Pt(6)

        def parse_markdown_blocks(content: str):
            """
            识别 Markdown 内容中的块级元素，返回结构化的 block 列表：
            - ('list', items)        items: [(kind, num_str, text), ...]
            - ('table', rows)        rows: [text, ...]
            - ('heading', level, text)
            - ('paragraph', text)
            """
            blocks = []
            lines = content.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].rstrip("\r").strip()
                if not line:
                    i += 1
                    continue

                # 列表项（有序/无序）
                if (
                    line.startswith("- ")
                    or line.startswith("* ")
                    or re.match(r"^\d+\.\s", line)
                ):
                    # items: (kind, number, text)
                    items = []
                    while i < len(lines):
                        raw = lines[i].rstrip("\r")
                        stripped = raw.strip()
                        # 无序列表
                        if stripped.startswith("- ") or stripped.startswith("* "):
                            text = re.sub(r"^[-*]\s+", "", stripped).strip()
                            if text:
                                items.append(("unordered", None, text))
                            i += 1
                            continue
                        # 有序列表（1. xxx）
                        m_num = re.match(r"^(\d+)\.\s+(.*)$", stripped)
                        if m_num:
                            num_str, text = m_num.groups()
                            text = text.strip()
                            if text:
                                items.append(("ordered", num_str, text))
                            i += 1
                            continue
                        break

                    if items:
                        blocks.append(("list", items))
                    continue

                # 表格（简化为每行一个段落，单元格用 | 分隔）
                if "|" in line:
                    rows = []
                    while i < len(lines):
                        raw = lines[i].rstrip("\r")
                        stripped = raw.strip()
                        if "|" in stripped:
                            # 跳过仅由 - 和 | 组成的分隔行
                            if not re.match(r"^\|?[-\s\|]+\|?$", stripped):
                                cells = [c.strip() for c in stripped.split("|")]
                                row_text = " | ".join([c for c in cells if c])
                                if row_text:
                                    rows.append(row_text)
                            i += 1
                        else:
                            break
                    if rows:
                        blocks.append(("table", rows))
                    continue

                # Markdown 标题（# / ## / ###）
                if line.startswith("#"):
                    m = re.match(r"^(#+)\s*(.*)$", line)
                    if m:
                        level_marks, title_text = m.groups()
                        level = min(len(level_marks), 3)
                        blocks.append(("heading", level, title_text.strip()))
                    i += 1
                    continue

                # 普通段落：合并连续的普通行
                para_lines = []
                while i < len(lines):
                    raw = lines[i].rstrip("\r")
                    stripped = raw.strip()
                    if (
                        stripped
                        and not stripped.startswith("-")
                        and not stripped.startswith("*")
                        and "|" not in stripped
                        and not stripped.startswith("#")
                    ):
                        para_lines.append(stripped)
                        i += 1
                    else:
                        break
                if para_lines:
                    text = " ".join(para_lines)
                    blocks.append(("paragraph", text))
                else:
                    i += 1

            return blocks

        def render_markdown_blocks(blocks) -> None:
            """将结构化的 Markdown blocks 渲染到文档"""
            for block in blocks:
                kind = block[0]
                if kind == "list":
                    items = block[1]
                    for item_kind, num_str, text in items:
                        p = doc.add_paragraph()
                        if item_kind == "unordered":
                            # 使用"• "模拟项目符号
                            run = p.add_run("• ")
                            set_run_font_simsun(run)
                        else:
                            # 有序列表：输出 "1. " 这样的前缀
                            prefix = f"{num_str}."
                            run = p.add_run(prefix + " ")
                            set_run_font_simsun(run)
                        # 紧跟在同一段落中追加列表文本
                        add_markdown_runs(p, text)
                elif kind == "table":
                    rows = block[1]
                    for row in rows:
                        add_markdown_paragraph(row)
                elif kind == "heading":
                    _, level, text = block
                    heading = doc.add_heading(text, level=level)
                    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    set_paragraph_font_simsun(heading)
                elif kind == "paragraph":
                    _, text = block
                    add_markdown_paragraph(text)

        def add_markdown_content(content: str) -> None:
            """解析并渲染 Markdown 文本到文档"""
            blocks = parse_markdown_blocks(content)
            render_markdown_blocks(blocks)

        binding_map: dict[str, dict] = {}
        if request.project_id:
            try:
                project_uuid = uuid.UUID(request.project_id)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的项目ID格式") from exc
            await _verify_project_member(project_uuid, current_user.id, db)
            result = await db.execute(
                select(ChapterMaterialBinding).where(ChapterMaterialBinding.project_id == project_uuid)
            )
            bindings = result.scalars().all()
            for binding in bindings:
                await db.refresh(binding, attribute_names=["material_asset"])
                material = binding.material_asset
                binding_map[str(binding.id)] = {
                    "caption": binding.caption or (material.name if material else "素材附件"),
                    "material_name": material.name if material else "素材附件",
                    "display_mode": binding.display_mode.value if hasattr(binding.display_mode, "value") else str(binding.display_mode),
                    "file_path": material.file_path if material else None,
                    "preview_path": material.preview_path if material else None,
                    "file_type": material.file_type if material else None,
                }

        # 递归构建文档内容（章节和内容）
        def add_outline_items(items, level: int = 1):
            for item in items:
                # 章节标题
                if level <= 3:
                    heading = doc.add_heading(f"{item.id} {item.title}", level=level)
                    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    for hr in heading.runs:
                        hr.font.name = "宋体"
                        rr = hr._element.rPr
                        if rr is not None and rr.rFonts is not None:
                            rr.rFonts.set(qn("w:eastAsia"), "宋体")
                else:
                    para = doc.add_paragraph()
                    run = para.add_run(f"{item.id} {item.title}")
                    run.bold = True
                    run.font.name = "宋体"
                    rr = run._element.rPr
                    if rr is not None and rr.rFonts is not None:
                        rr.rFonts.set(qn("w:eastAsia"), "宋体")
                    para.paragraph_format.space_before = Pt(6)
                    para.paragraph_format.space_after = Pt(3)

                # 叶子节点内容
                if not item.children:
                    content = item.content or ""
                    if content.strip():
                        render_content_with_material_bindings(
                            document=doc,
                            content=content,
                            binding_map=binding_map,
                            add_text=add_markdown_content,
                        )
                else:
                    add_outline_items(item.children, level + 1)

        add_outline_items(request.outline)

        # 输出到内存并返回
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        filename = f"{request.project_name or '标书文档'}.docx"
        # 使用 RFC 5987 格式对文件名进行 URL 编码，避免非 ASCII 字符导致的编码错误
        encoded_filename = quote(filename)
        content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
        headers = {"Content-Disposition": content_disposition}

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers=headers,
        )
    except Exception as e:
        import traceback

        logger_msg = f"导出Word失败: {str(e)}"
        print(logger_msg)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="导出Word失败，请稍后重试")


# ============ 项目上下文版本的接口 ============


async def _verify_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Project:
    """验证用户是项目成员并返回项目"""
    # 检查用户是否是项目成员
    member_exists = await db.execute(
        select(
            exists().where(
                and_(
                    project_members.c.project_id == project_id,
                    project_members.c.user_id == user_id,
                )
            )
        )
    )
    if not member_exists.scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或您没有访问权限",
        )

    # 获取项目
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在",
        )
    return project


@router.post("/upload-to-project", response_model=ProjectFileUploadResponse)
async def upload_file_to_project(
    project_id: Annotated[str, Form(...)],
    file: UploadFile = File(...),
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """上传文档文件到指定项目，提取文本内容并保存到项目记录"""
    try:
        # 验证 project_id 格式
        try:
            project_uuid = uuid.UUID(project_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的项目ID格式",
            )

        # 验证用户是项目成员
        project = await _verify_project_member(project_uuid, current_user.id, db)

        # 检查文件类型（Content-Type + magic bytes 双重校验）
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的文件类型，请上传PDF或Word文档",
            )

        # Magic bytes 校验：防止伪造 Content-Type
        header = await file.read(8)
        await file.seek(0)
        is_pdf = header[:5] == b"%PDF-"
        is_docx = header[:4] == b"PK\x03\x04"  # docx 本质是 ZIP
        if not (is_pdf or is_docx):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容与类型不匹配，请上传有效的PDF或Word文档",
            )

        # 处理文件并提取文本
        file_content = await FileService.process_uploaded_file(file)

        # 保存文件内容到项目记录
        project.file_content = file_content
        await db.flush()
        await db.refresh(project)

        return ProjectFileUploadResponse(
            success=True,
            message=f"文件 {file.filename} 已上传并保存到项目",
            project_id=str(project.id),
            file_content_length=len(file_content),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件处理失败: {str(e)}",
        )


@router.post("/analyze-project-stream")
async def analyze_project_document_stream(
    request: ProjectAnalysisRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """流式分析项目文档内容，并将分析结果保存到项目记录"""
    from ..db.database import async_session_factory

    try:
        # 验证 project_id 格式
        try:
            project_uuid = uuid.UUID(request.project_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的项目ID格式",
            )

        # 验证用户是项目成员并获取项目
        project = await _verify_project_member(project_uuid, current_user.id, db)

        # 检查项目是否有文件内容
        if not project.file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="项目尚未上传文档，请先上传招标文件",
            )

        # 创建OpenAI服务实例，从数据库加载配置
        openai_service = OpenAIService(db=db, project_id=project_uuid)
        if request.provider_config_id:
            configured = await openai_service.use_config_by_id(request.provider_config_id)
            if not configured:
                raise HTTPException(status_code=404, detail="所选 Provider 配置不存在")
        else:
            await openai_service._ensure_initialized()

        if not openai_service.api_key:
            raise HTTPException(status_code=400, detail="请先配置OpenAI API密钥")

        # 如果前端传了模型名称，覆盖默认模型
        if request.model_name:
            openai_service.set_model(request.model_name)

        # 用于收集分析结果的变量
        collected_result = []

        # 保存分析结果的变量
        analysis_type = request.analysis_type
        project_id = project_uuid

        async def generate():
            nonlocal collected_result

            # 使用 PromptService 获取提示词
            prompt_service = PromptService(db)
            scene_key = {
                AnalysisType.OVERVIEW: "doc_analysis_overview",
                AnalysisType.REQUIREMENTS: "doc_analysis_requirements",
                AnalysisType.MATERIAL_REQUIREMENTS: "doc_analysis_requirements",
            }[analysis_type]
            prompt, _ = await prompt_service.get_prompt(scene_key, project_id)
            system_prompt, user_template = PromptService.split_prompt(prompt)
            user_prompt = prompt_service.render_prompt(
                user_template, {"file_content": project.file_content}
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # 流式返回分析结果，同时收集完整结果
            async for chunk in openai_service.stream_chat_completion(
                messages, temperature=0.3
            ):
                collected_result.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"

            # 在生成器内部创建新的数据库会话保存结果
            full_result = "".join(collected_result)
            async with async_session_factory() as save_db:
                try:
                    # 重新查询项目
                    save_project = await save_db.get(Project, project_id)
                    if save_project:
                        if analysis_type == AnalysisType.OVERVIEW:
                            save_project.project_overview = full_result
                        else:
                            save_project.tech_requirements = full_result
                        await save_db.commit()
                except Exception as e:
                    print(f"保存分析结果失败: {e}")

            # 发送结束信号
            yield "data: [DONE]\n\n"

        return sse_response(generate())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档分析失败: {str(e)}",
        )


class ProjectAnalysisResult(BaseModel):
    """项目分析结果响应"""

    project_id: str
    file_content: str | None = None
    project_overview: str | None = None
    tech_requirements: str | None = None
    file_content_length: int = Field(..., description="文件内容字符数")


@router.get("/project-analysis/{project_id}", response_model=ProjectAnalysisResult)
async def get_project_analysis(
    project_id: uuid.UUID,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """获取项目的文档分析结果"""
    # 验证用户是项目成员并获取项目
    project = await _verify_project_member(project_id, current_user.id, db)

    return ProjectAnalysisResult(
        project_id=str(project.id),
        file_content=project.file_content,
        project_overview=project.project_overview,
        tech_requirements=project.tech_requirements,
        file_content_length=len(project.file_content) if project.file_content else 0,
    )


class SaveAnalysisRequest(BaseModel):
    """保存分析结果请求"""
    project_overview: str | None = None
    tech_requirements: str | None = None


@router.post("/save-analysis/{project_id}")
async def save_project_analysis(
    project_id: uuid.UUID,
    request: SaveAnalysisRequest,
    current_user: Annotated[User, Depends(require_editor)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """手动保存项目的文档分析结果（用于下一步前的备份保存）"""
    # 验证用户是项目成员并获取项目
    project = await _verify_project_member(project_id, current_user.id, db)

    # 保存分析结果
    if request.project_overview is not None:
        project.project_overview = request.project_overview
    if request.tech_requirements is not None:
        project.tech_requirements = request.tech_requirements

    await db.commit()

    return {"success": True, "message": "分析结果已保存"}


# ============ 素材解析：文本与图片分离 ============


@router.post("/parse-material", response_model=MaterialParseResponse)
async def parse_material(
    file: UploadFile = File(...),
    current_user: Annotated[User, Depends(require_editor)] = None,
):
    """
    上传素材文件并解析，将文本和图片分离返回。

    返回的 text 字段包含纯文本内容（图片位置以 [图片N] 标记），
    images 字段包含所有提取的图片信息（路径、格式、大小等），
    可通过 /api/document/material-image/{material_id}/{filename} 获取图片文件。
    """
    # 检查文件类型
    allowed_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的文件类型，请上传PDF或Word文档",
        )

    # Magic bytes 校验
    header = await file.read(8)
    await file.seek(0)
    is_pdf = header[:5] == b"%PDF-"
    is_docx = header[:4] == b"PK\x03\x04"
    if not (is_pdf or is_docx):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容与类型不匹配，请上传有效的PDF或Word文档",
        )

    # 文件大小预检（peek content_length）
    try:
        result = await FileService.parse_material(file)
    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        if "大小超过限制" in err_msg:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=err_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"素材解析失败: {err_msg}",
        )

    # 写入所有者元数据，供 GET /material-image 鉴权使用
    await FileService.write_material_owner(result["material_id"], str(current_user.id))

    return MaterialParseResponse(
        success=True,
        message=f"素材解析成功，共提取 {len(result['images'])} 张图片",
        material_id=result["material_id"],
        source_filename=result["source_filename"],
        text=result["text"],
        images=[MaterialImageInfo(**img) for img in result["images"]],
        image_count=len(result["images"]),
    )


@router.get("/material-image/{material_id}/{filename}")
async def get_material_image(
    material_id: str,
    filename: str,
    current_user: Annotated[User, Depends(require_editor)] = None,
):
    """获取素材解析提取的图片文件（仅限解析该素材的本人访问）"""
    # 路径穿越防护：material_id 和 filename 均不得包含路径分隔符
    if os.sep in material_id or "/" in material_id or ".." in material_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的素材ID")
    if os.sep in filename or "/" in filename or ".." in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的文件名")

    image_path = os.path.join(
        settings.upload_dir,
        "material_images",
        material_id,
        filename,
    )

    # 安全检查：防止路径遍历（double check with realpath）
    real_path = os.path.realpath(image_path)
    real_base = os.path.realpath(os.path.join(settings.upload_dir, "material_images"))
    if not real_path.startswith(real_base + os.sep) and real_path != real_base:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件")

    if not os.path.exists(real_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片文件不存在")

    # 越权校验：图片必须属于当前登录用户
    owner_id = FileService.read_material_owner(material_id)
    if owner_id is None:
        # 无所有者元数据（旧数据或异常情况）
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件")
    if owner_id != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件")

    # 根据扩展名设置 MIME 类型
    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    media_type = mime_map.get(ext, "application/octet-stream")

    return FileResponse(real_path, media_type=media_type, filename=filename)
