"""Word 批注生成服务"""
import os
import copy
import io
from datetime import datetime
from typing import Any

from docx import Document
from lxml import etree

from ..config import settings

# Word 批注所需的 XML 命名空间
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class WordCommentService:
    """Word 批注生成服务"""

    def __init__(self):
        self._comment_id_counter = 0

    def _next_comment_id(self) -> int:
        """生成递增的批注 ID"""
        self._comment_id_counter += 1
        return self._comment_id_counter

    @staticmethod
    def _format_responsiveness_comment(item: dict) -> str:
        """格式化响应性审查批注内容"""
        lines = ["【AI 标书审查 - 响应性】"]
        lines.append(f"评分项：{item.get('rating_item', '')}")
        lines.append(f"覆盖状态：{_coverage_status_label(item.get('coverage_status', ''))}")
        lines.append("")

        evidence = item.get("evidence", "")
        if evidence:
            lines.append(f"证据说明：{evidence}")
            lines.append("")

        issues = item.get("issues", [])
        if issues:
            lines.append("存在问题：")
            for i, issue in enumerate(issues, 1):
                lines.append(f"{i}. {issue}")
            lines.append("")

        suggestions = item.get("suggestions", [])
        if suggestions:
            lines.append("修改建议：")
            for i, suggestion in enumerate(suggestions, 1):
                lines.append(f"{i}. {suggestion}")
            lines.append("")

        rewrite = item.get("rewrite_suggestions", [])
        if rewrite:
            lines.append("参考改写：")
            for r in rewrite:
                lines.append(r)
            lines.append("")

        confidence = item.get("confidence", "medium")
        lines.append(f"置信度：{_confidence_label(confidence)}")

        return "\n".join(lines)

    @staticmethod
    def _format_compliance_comment(item: dict) -> str:
        """格式化合规性审查批注内容"""
        lines = ["【AI 标书审查 - 合规性】"]
        lines.append(f"类别：{item.get('compliance_category', '')}")
        lines.append(f"检查结果：{_check_result_label(item.get('check_result', ''))}")
        lines.append("")

        clause = item.get("clause_text", "")
        if clause:
            lines.append(f"招标条款：{clause}")
            lines.append("")

        detail = item.get("detail", "")
        if detail:
            lines.append(f"检查说明：{detail}")
            lines.append("")

        suggestion = item.get("suggestion", "")
        if suggestion:
            lines.append(f"修改建议：{suggestion}")
            lines.append("")

        severity = item.get("severity", "warning")
        lines.append(f"严重程度：{_severity_label(severity)}")

        return "\n".join(lines)

    @staticmethod
    def _format_consistency_comment(item: dict) -> str:
        """格式化一致性审查批注内容"""
        lines = ["【AI 标书审查 - 一致性】"]
        lines.append(f"类别：{item.get('category', '')}")
        lines.append(f"问题描述：{item.get('description', '')}")
        lines.append("")
        lines.append(f"章节A：{item.get('chapter_a', '')}")
        lines.append(f"  内容：{item.get('detail_a', '')}")
        lines.append(f"章节B：{item.get('chapter_b', '')}")
        lines.append(f"  内容：{item.get('detail_b', '')}")
        lines.append("")

        suggestion = item.get("suggestion", "")
        if suggestion:
            lines.append(f"修改建议：{suggestion}")
            lines.append("")

        severity = item.get("severity", "warning")
        lines.append(f"严重程度：{_severity_label(severity)}")

        return "\n".join(lines)

    def _find_paragraph_index(
        self,
        paragraph_index: list[dict],
        chapter_targets: list[str],
    ) -> int | None:
        """
        根据 chapter_targets 在段落索引中查找匹配的段落位置。

        策略：
        1. 精确匹配章节标题
        2. 模糊匹配（包含关系）
        3. 兜底：返回 None
        """
        if not paragraph_index or not chapter_targets:
            return None

        for target in chapter_targets:
            target_lower = target.strip().lower()
            for entry in paragraph_index:
                text = entry.get("text", "").strip()
                entry_type = entry.get("type", "")

                # 优先匹配标题
                if entry_type == "heading":
                    if text.lower() == target_lower or target_lower in text.lower():
                        return entry.get("index")

            # 模糊匹配：在任何段落中查找包含关系
            for entry in paragraph_index:
                text = entry.get("text", "").strip()
                if target_lower in text.lower() and len(text) < len(target) + 20:
                    return entry.get("index")

        return None

    def export_reviewed_document(
        self,
        bid_file_path: str,
        responsiveness: dict | None = None,
        compliance: dict | None = None,
        consistency: dict | None = None,
        author: str = "AI 标书审查",
    ) -> str:
        """
        在原始投标文件上添加审查批注，返回新文件路径。

        Args:
            bid_file_path: 原始投标文件路径
            responsiveness: 响应性审查结果
            compliance: 合规性审查结果
            consistency: 一致性审查结果
            author: 批注作者

        Returns:
            生成的带批注文件路径
        """
        if not os.path.exists(bid_file_path):
            raise FileNotFoundError(f"投标文件不存在: {bid_file_path}")

        doc = Document(bid_file_path)
        paragraphs = doc.paragraphs

        if not paragraphs:
            raise ValueError("投标文件没有可解析的段落")

        # 收集所有待添加的批注：(paragraph_index, comment_text)
        comments_to_add: list[tuple[int, str]] = []

        # 响应性批注
        if responsiveness:
            items = responsiveness.get("items", [])
            for item in items:
                comment_text = self._format_responsiveness_comment(item)
                chapter_targets = item.get("chapter_targets", [])
                # 使用 AI 返回的引用来确定位置（简化版）
                para_idx = self._find_paragraph_index_for_item(
                    paragraphs, item, chapter_targets
                )
                if para_idx is not None:
                    comments_to_add.append((para_idx, comment_text))

        # 合规性批注
        if compliance:
            items = compliance.get("items", [])
            for item in items:
                comment_text = self._format_compliance_comment(item)
                # 合规性批注：尝试在文档开头或封面区域添加
                # 由于合规性通常不针对特定段落，添加到第一个有内容的段落
                comments_to_add.append((0, comment_text))

        # 一致性批注
        if consistency:
            contradictions = consistency.get("contradictions", [])
            for item in contradictions:
                comment_text = self._format_consistency_comment(item)
                chapter_a = item.get("chapter_a", "")
                chapter_b = item.get("chapter_b", "")
                para_idx = self._find_paragraph_by_chapter_name(
                    paragraphs, chapter_a
                )
                if para_idx is None:
                    para_idx = self._find_paragraph_by_chapter_name(
                        paragraphs, chapter_b
                    )
                if para_idx is None:
                    para_idx = 0
                comments_to_add.append((para_idx, comment_text))

        # 去重：同一段落只保留一条批注（合并内容）
        merged: dict[int, str] = {}
        for idx, text in comments_to_add:
            if idx in merged:
                merged[idx] += "\n\n---\n\n" + text
            else:
                merged[idx] = text

        # 按段落索引排序
        sorted_comments = sorted(merged.items())

        # 添加批注到文档
        for para_idx, comment_text in sorted_comments:
            if para_idx < len(paragraphs):
                self._add_comment_to_paragraph(
                    doc, paragraphs[para_idx], comment_text, author
                )

        # 保存新文件
        base_name = os.path.splitext(os.path.basename(bid_file_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(settings.upload_dir, "review_export")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{base_name}_审查批注_{timestamp}.docx")

        doc.save(output_path)
        return output_path

    def _find_paragraph_index_for_item(
        self,
        paragraphs: list,
        item: dict,
        chapter_targets: list[str],
    ) -> int | None:
        """根据评分项的 chapter_targets 在文档段落中查找匹配位置"""
        if not chapter_targets:
            return None

        for target in chapter_targets:
            for i, para in enumerate(paragraphs):
                text = para.text.strip()
                if not text:
                    continue
                # 检查是否是标题样式
                if para.style and para.style.name and "Heading" in para.style.name:
                    if target.strip() in text:
                        return i
                # 模糊匹配
                if target.strip() in text and len(text) < 100:
                    return i
        return None

    def _find_paragraph_by_chapter_name(
        self,
        paragraphs: list,
        chapter_name: str,
    ) -> int | None:
        """根据章节名称在文档段落中查找"""
        if not chapter_name:
            return None
        for i, para in enumerate(paragraphs):
            text = para.text.strip()
            if not text:
                continue
            if chapter_name.strip() in text and len(text) < 100:
                return i
        return None

    @staticmethod
    def _add_comment_to_paragraph(
        doc: Document,
        paragraph: Any,
        comment_text: str,
        author: str,
    ) -> None:
        """
        在指定段落添加 Word 批注。
        使用 python-docx 的底层 XML 操作。
        """
        # 获取或创建 comments part
        comments_part = WordCommentService._ensure_comments_part(doc)

        # 生成批注 ID
        comment_id = len(comments_part.element.findall(f"{{{WORD_NS}}}comment")) + 1

        # 创建 comment 元素
        comment_el = WordCommentService._create_comment_element(
            comment_id, comment_text, author
        )
        comments_part.element.append(comment_el)

        # 在段落中插入批注标记
        paragraph_element = paragraph._element
        p = paragraph_element

        # 查找或创建第一个 run
        runs = p.findall(f"{{{WORD_NS}}}r")
        if not runs:
            # 如果段落没有 run，创建一个空 run
            run = etree.SubElement(p, f"{{{WORD_NS}}}r")
            etree.SubElement(run, f"{{{WORD_NS}}}t")
            runs = [run]

        first_run = runs[0]

        # 插入 commentRangeStart
        id_attr = f"{{{WORD_NS}}}id"
        comment_range_start = etree.Element(f"{{{WORD_NS}}}commentRangeStart")
        comment_range_start.set(id_attr, str(comment_id))
        p.insert(list(p).index(first_run), comment_range_start)

        # 插入 commentRangeEnd（在最后一个 run 之后）
        last_run = runs[-1]
        comment_range_end = etree.Element(f"{{{WORD_NS}}}commentRangeEnd")
        comment_range_end.set(id_attr, str(comment_id))
        idx = list(p).index(last_run) + 1
        p.insert(idx, comment_range_end)

        # 插入 commentReference
        comment_ref_run = etree.SubElement(p, f"{{{WORD_NS}}}r")
        comment_ref_start = etree.SubElement(
            comment_ref_run, f"{{{WORD_NS}}}rPr"
        )
        comment_ref_style = etree.SubElement(
            comment_ref_start, f"{{{WORD_NS}}}rStyle"
        )
        comment_ref_style.set(f"{{{WORD_NS}}}val", "CommentReference")
        comment_ref = etree.SubElement(
            comment_ref_run, f"{{{WORD_NS}}}commentReference"
        )
        comment_ref.set(id_attr, str(comment_id))

        # 建立关系
        from docx.opc.constants import RELATIONSHIP_TYPE as RT
        from docx.opc.part import Part

        # 检查是否已经建立了 comments part 的关系
        document_part = doc.part
        rel_id = None
        for rel in document_part.rels.values():
            if "comments.xml" in rel.target_ref:
                rel_id = rel.rId
                break

        if rel_id is None:
            rel_id = document_part.relate_to(comments_part, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments")

    @staticmethod
    def _ensure_comments_part(doc: Document) -> Any:
        """确保文档有 comments.xml part"""
        from docx.opc.part import Part
        from docx.opc.constants import CONTENT_TYPE as CT

        document_part = doc.part

        # 检查是否已存在 comments part
        for rel in document_part.rels.values():
            if "comments.xml" in rel.target_ref:
                return rel.target_part

        # 创建新的 comments part
        from docx.parts.styles import StylesPart
        comments_xml = f'<w:comments xmlns:w="{WORD_NS}" xmlns:r="{REL_NS}"></w:comments>'
        comments_element = etree.fromstring(comments_xml)

        # 使用正确的 content type
        from docx.parts.document import DocumentPart
        comments_part = Part(
            "/word/comments.xml",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
            comments_element,
            document_part.package,
        )

        return comments_part

    @staticmethod
    def _create_comment_element(
        comment_id: int,
        text: str,
        author: str,
    ) -> Any:
        """创建 Word 批注 XML 元素"""
        comment = etree.Element(f"{{{WORD_NS}}}comment")
        comment.set(f"{{{WORD_NS}}}id", str(comment_id))
        comment.set(f"{{{WORD_NS}}}author", author)
        comment.set(f"{{{WORD_NS}}}date", datetime.now().isoformat())

        # 添加初始段落
        p = etree.SubElement(comment, f"{{{WORD_NS}}}p")

        # 将文本按行分割，每行一个 run
        for i, line in enumerate(text.split("\n")):
            if i > 0:
                # 换行
                p = etree.SubElement(comment, f"{{{WORD_NS}}}p")

            run = etree.SubElement(p, f"{{{WORD_NS}}}r")
            t = etree.SubElement(run, f"{{{WORD_NS}}}t")
            t.text = line
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")

        return comment


def _coverage_status_label(status: str) -> str:
    """覆盖状态中文标签"""
    labels = {
        "covered": "已覆盖",
        "partial": "部分覆盖",
        "missing": "未覆盖",
        "risk": "有风险",
    }
    return labels.get(status, status)


def _check_result_label(result: str) -> str:
    """检查结果中文标签"""
    labels = {"pass": "通过", "warning": "警告", "fail": "不通过"}
    return labels.get(result, result)


def _severity_label(severity: str) -> str:
    """严重程度中文标签"""
    labels = {"critical": "高", "warning": "中", "info": "低"}
    return labels.get(severity, severity)


def _confidence_label(confidence: str) -> str:
    """置信度中文标签"""
    labels = {"high": "高", "medium": "中", "low": "低"}
    return labels.get(confidence, confidence)
