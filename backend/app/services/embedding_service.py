"""Ollama 嵌入服务"""
import logging
import os
from typing import List, Optional
import httpx

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Ollama 本地嵌入服务

    使用 Ollama API 生成文本嵌入向量
    默认模型: qwen3-embedding:4b (2560 维度)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
    ):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("EMBEDDING_MODEL", "qwen3-embedding:4b")
        self.dimension = dimension or int(os.getenv("EMBEDDING_DIMENSION", "2560"))
        self.timeout = 60.0

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """获取单个文本的嵌入向量"""
        embeddings = await self.get_embeddings([text])
        return embeddings[0] if embeddings else None

    async def get_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """批量获取嵌入向量"""
        if not texts:
            return []

        results = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for text in texts:
                try:
                    response = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={
                            "model": self.model,
                            "prompt": text,
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    embedding = data.get("embedding")
                    results.append(embedding)
                except Exception as e:
                    logger.error(f"获取嵌入失败: {str(e)}")
                    results.append(None)

        return results

    async def is_available(self) -> bool:
        """检查 Ollama 服务是否可用"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
