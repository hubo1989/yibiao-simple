"""PageIndex 索引服务"""
import os
import sys
import json
import asyncio
import logging
from typing import Optional
from pathlib import Path

import aiofiles
from sqlalchemy import select

from ..config import settings
from ..models.api_key_config import ApiKeyConfig
from ..utils.encryption import encryption_service

logger = logging.getLogger(__name__)

# 确保 PageIndex 模块可导入
_pageindex_dir = os.path.join(os.path.dirname(__file__), "../../PageIndex")
if _pageindex_dir not in sys.path:
    sys.path.insert(0, _pageindex_dir)


class PageIndexService:
    """PageIndex 索引服务 - 处理 PDF 和 Markdown 文件，生成树状索引"""

    def __init__(self, db=None):
        self._db = db
        self.pageindex_dir = _pageindex_dir
        self.model = os.getenv("PAGEINDEX_MODEL", "gpt-4o-2024-11-20")
        self.timeout = int(os.getenv("PAGEINDEX_TIMEOUT", "1800"))
        self.api_key = None
        self.base_url = None

    async def _load_config(self) -> bool:
        """从数据库加载默认 API Key 配置"""
        if self._db is None:
            return False

        try:
            result = await self._db.execute(
                select(ApiKeyConfig).where(ApiKeyConfig.is_default == True).limit(1)
            )
            config = result.scalar_one_or_none()

            if config:
                self.api_key = encryption_service.decrypt(config.api_key_encrypted)
                self.base_url = config.base_url
                self.model = config.get_index_model_name() or self.model
                logger.info(f"从数据库加载 API 配置: provider={config.provider}, model={self.model}")
                return True
            else:
                logger.warning("数据库中没有默认的 API Key 配置")
                return False
        except Exception as e:
            logger.error(f"加载 API 配置失败: {e}")
            return False

    def _setup_env(self):
        """设置 PageIndex 需要的环境变量"""
        os.environ["CHATGPT_API_KEY"] = self.api_key
        os.environ["OPENAI_API_KEY"] = self.api_key
        if self.base_url:
            os.environ["OPENAI_BASE_URL"] = self.base_url

    async def process_pdf(self, pdf_path: str) -> dict:
        """
        处理 PDF 文件，生成 PageIndex 树（直接调用内部异步函数，避免 asyncio.run 冲突）

        Args:
            pdf_path: PDF 文件路径

        Returns:
            PageIndex 树状索引（JSON格式）
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        await self._load_config()
        if not self.api_key:
            raise Exception("未配置 API Key，请在设置页面添加 API Key 配置")

        logger.info(f"开始处理 PDF 文件: {pdf_path}, model={self.model}")

        try:
            self._setup_env()

            from pageindex.page_index import tree_parser
            from pageindex.utils import (
                ConfigLoader, get_page_tokens, write_node_id,
                add_node_text, generate_summaries_for_structure,
                remove_structure_text, get_pdf_name, JsonLogger,
            )

            config_loader = ConfigLoader()
            opt = config_loader.load({
                "model": self.model,
                "if_add_node_id": "yes",
                "if_add_node_summary": "yes",
            })

            # 同步的 PDF 解析放到线程池
            loop = asyncio.get_event_loop()
            pi_logger = JsonLogger(pdf_path)
            page_list = await loop.run_in_executor(None, get_page_tokens, pdf_path)
            logger.info(f"PDF 解析完成: {len(page_list)} 页")

            # 异步的 tree_parser + summary 直接 await，不经过 asyncio.run()
            structure = await asyncio.wait_for(
                tree_parser(page_list, opt, doc=pdf_path, logger=pi_logger),
                timeout=self.timeout
            )

            if opt.if_add_node_id == 'yes':
                write_node_id(structure)
            if opt.if_add_node_text == 'yes':
                add_node_text(structure, page_list)
            if opt.if_add_node_summary == 'yes':
                if opt.if_add_node_text == 'no':
                    add_node_text(structure, page_list)
                await generate_summaries_for_structure(structure, model=opt.model)
                if opt.if_add_node_text == 'no':
                    remove_structure_text(structure)

            result = {
                'doc_name': get_pdf_name(pdf_path),
                'structure': structure,
            }

            logger.info(f"PDF 处理完成: {pdf_path}")
            return result

        except asyncio.TimeoutError:
            raise Exception(f"PageIndex 处理超时（{self.timeout}秒）")
        except Exception as e:
            logger.error(f"处理 PDF 出错: {str(e)}", exc_info=True)
            raise

    async def process_markdown(self, md_path: str) -> dict:
        """
        处理 Markdown 文件，生成 PageIndex 树（进程内直接调用）

        Args:
            md_path: Markdown 文件路径

        Returns:
            PageIndex 树状索引（JSON格式）
        """
        if not os.path.exists(md_path):
            raise FileNotFoundError(f"Markdown 文件不存在: {md_path}")

        await self._load_config()
        if not self.api_key:
            raise Exception("未配置 API Key，请在设置页面添加 API Key 配置")

        logger.info(f"开始处理 Markdown 文件: {md_path}, model={self.model}")

        try:
            self._setup_env()

            from pageindex.page_index_md import md_to_tree
            from pageindex.utils import ConfigLoader

            config_loader = ConfigLoader()
            opt = config_loader.load({
                "model": self.model,
                "if_add_node_id": "yes",
                "if_add_node_summary": "yes",
            })

            result = await asyncio.wait_for(
                md_to_tree(
                    md_path=md_path,
                    if_thinning=False,
                    min_token_threshold=5000,
                    if_add_node_summary=opt.if_add_node_summary,
                    summary_token_threshold=200,
                    model=opt.model,
                    if_add_doc_description=opt.if_add_doc_description,
                    if_add_node_text=opt.if_add_node_text,
                    if_add_node_id=opt.if_add_node_id,
                ),
                timeout=self.timeout
            )

            logger.info(f"Markdown 处理完成: {md_path}")
            return result

        except asyncio.TimeoutError:
            raise Exception(f"PageIndex 处理超时（{self.timeout}秒）")
        except Exception as e:
            logger.error(f"处理 Markdown 出错: {str(e)}", exc_info=True)
            raise

    async def convert_docx_to_pdf(self, docx_path: str) -> str:
        """将 DOCX/DOC 转换为 PDF"""
        if not os.path.exists(docx_path):
            raise FileNotFoundError(f"Word 文件不存在: {docx_path}")

        logger.info(f"开始转换 Word 到 PDF: {docx_path}")

        pdf_path = docx_path.rsplit('.', 1)[0] + '.pdf'

        if os.path.exists(pdf_path):
            logger.info(f"PDF 文件已存在: {pdf_path}")
            return pdf_path

        libreoffice_cmds = ["soffice", "libreoffice"]
        libreoffice_path = None

        for cmd in libreoffice_cmds:
            try:
                result = await asyncio.create_subprocess_exec(
                    "which", cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await result.communicate()
                if result.returncode == 0:
                    libreoffice_path = stdout.decode().strip() or cmd
                    logger.info(f"找到 LibreOffice: {libreoffice_path}")
                    break
            except Exception:
                continue

        if not libreoffice_path:
            logger.warning("LibreOffice 未找到，尝试 docx2pdf")
            return await self._convert_with_docx2pdf(docx_path, pdf_path)

        try:
            output_dir = os.path.dirname(docx_path)
            cmd = [
                libreoffice_path,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", output_dir,
                docx_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0 and os.path.exists(pdf_path):
                logger.info(f"使用 LibreOffice 转换成功: {pdf_path}")
                return pdf_path

            error_msg = stderr.decode() if stderr else "未知错误"
            logger.warning(f"LibreOffice 转换失败: {error_msg}，尝试 docx2pdf")
            return await self._convert_with_docx2pdf(docx_path, pdf_path)

        except Exception as e:
            logger.error(f"LibreOffice 转换失败: {str(e)}")
            return await self._convert_with_docx2pdf(docx_path, pdf_path)

    async def _convert_with_docx2pdf(self, docx_path: str, pdf_path: str) -> str:
        """使用 docx2pdf 库转换"""
        try:
            from docx2pdf import convert

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, convert, docx_path, pdf_path)

            if not os.path.exists(pdf_path):
                raise Exception("docx2pdf 转换失败：PDF 文件未生成")

            logger.info(f"使用 docx2pdf 转换成功: {pdf_path}")
            return pdf_path

        except ImportError:
            raise Exception(
                "DOCX 转 PDF 需要安装 LibreOffice 或 docx2pdf。\n"
                "安装方式：\n"
                "1. LibreOffice: https://www.libreoffice.org/download\n"
                "2. docx2pdf: pip install docx2pdf (仅 Windows)"
            )
        except Exception as e:
            raise Exception(f"DOCX 转 PDF 失败: {str(e)}")

    async def save_as_markdown(self, content: str, title: str, output_path: str) -> str:
        """将手动内容保存为 Markdown 文件"""
        md_content = f"# {title}\n\n{content}"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
            await f.write(md_content)

        logger.info(f"Markdown 文件已保存: {output_path}")
        return output_path
