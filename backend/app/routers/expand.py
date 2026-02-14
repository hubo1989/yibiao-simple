"""标书扩写相关API路由"""

from typing import Annotated

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from ..models.schemas import FileUploadResponse
from ..models.user import User
from ..services.file_service import FileService
from ..utils import prompt_manager
from ..services.openai_service import OpenAIService
from ..auth.dependencies import require_editor

router = APIRouter(prefix="/api/expand", tags=["标书扩写"])

# 文件 Magic Bytes 签名
PDF_MAGIC = b"%PDF-"
DOCX_MAGIC = b"PK\x03\x04"


def validate_file_magic_bytes(content: bytes, filename: str) -> tuple[bool, str]:
    """
    通过 Magic Bytes 验证文件真实类型

    Returns:
        (is_valid, error_message)
    """
    if content.startswith(PDF_MAGIC):
        return True, ""
    elif content.startswith(DOCX_MAGIC):
        return True, ""
    else:
        return (
            False,
            f"文件 {filename} 的实际内容与声明的类型不符，请上传有效的 PDF 或 Word 文档",
        )


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: Annotated[User, Depends(require_editor)] = None,
):
    """上传文档文件并提取文本内容"""
    try:
        # 检查文件类型
        allowed_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]

        if file.content_type not in allowed_types:
            return FileUploadResponse(
                success=False, message="不支持的文件类型，请上传PDF或Word文档"
            )

        # 读取文件内容进行 Magic Bytes 校验
        content = await file.read()

        is_valid, error_msg = validate_file_magic_bytes(
            content, file.filename or "unknown"
        )
        if not is_valid:
            return FileUploadResponse(success=False, message=error_msg)

        # 重置文件指针以供后续处理
        await file.seek(0)

        # 处理文件并提取文本
        file_content = await FileService.process_uploaded_file(file)

        # 提取目录
        openai_service = OpenAIService()
        messages = [
            {"role": "system", "content": prompt_manager.read_expand_outline_prompt()},
            {"role": "user", "content": file_content},
        ]
        full_content = ""
        async for chunk in openai_service.stream_chat_completion(
            messages, temperature=0.7, response_format={"type": "json_object"}
        ):
            full_content += chunk
        return FileUploadResponse(
            success=True,
            message=f"文件 {file.filename} 上传成功",
            file_content=file_content,
            old_outline=full_content,
        )

    except Exception as e:
        return FileUploadResponse(success=False, message=f"文件处理失败: {str(e)}")
