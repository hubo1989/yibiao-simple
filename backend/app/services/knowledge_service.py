"""知识库服务 - 文本分块和 TF-IDF 检索"""
import re
import math
import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.knowledge import KnowledgeDoc, DocType, EmbeddingStatus


# 中英文停用词（简化版）
STOP_WORDS = {
    # 中文停用词
    "的", "是", "在", "了", "和", "与", "或", "有", "为", "以", "及", "等", "到", "对", "也",
    "这", "那", "我", "你", "他", "她", "它", "们", "个", "上", "下", "中", "来", "去", "说",
    "要", "会", "能", "就", "不", "都", "而", "但", "如", "因", "由", "被", "把", "让", "给",
    # 英文停用词
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "must", "shall", "can", "need", "dare", "ought", "used",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into",
    "through", "during", "before", "after", "above", "below", "between", "under",
    "and", "but", "or", "nor", "so", "yet", "both", "either", "neither",
    "not", "only", "own", "same", "than", "too", "very", "just", "also",
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "been", "being", "here", "there", "when", "where", "why", "how",
    "all", "each", "few", "more", "most", "other", "some", "such", "no",
}


def tokenize(text: str) -> list[str]:
    """
    文本分词（支持中英文）
    - 中文：按字符切分
    - 英文：按空格和标点切分，转小写
    """
    tokens = []

    # 分离中英文
    # 匹配连续的中文或连续的英文单词
    pattern = r'[\u4e00-\u9fff]+|[a-zA-Z]+'

    for match in re.finditer(pattern, text.lower()):
        word = match.group()
        # 中文按字符切分（简化处理，实际应使用分词库）
        if re.match(r'^[\u4e00-\u9fff]+$', word):
            # 对于中文，使用简单的二元切分（bi-gram）
            if len(word) >= 2:
                for i in range(len(word) - 1):
                    tokens.append(word[i:i+2])
            tokens.extend(list(word))
        else:
            # 英文单词
            if len(word) >= 2:
                tokens.append(word)

    return tokens


def remove_stop_words(tokens: list[str]) -> list[str]:
    """移除停用词"""
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """提取关键词（基于词频）"""
    tokens = tokenize(text)
    tokens = remove_stop_words(tokens)

    if not tokens:
        return []

    # 统计词频
    counter = Counter(tokens)

    # 返回前 N 个高频词
    return [word for word, _ in counter.most_common(top_n)]


def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[dict[str, Any]]:
    """
    将文本分块

    Args:
        text: 原始文本
        chunk_size: 每块的最大字符数
        overlap: 块之间的重叠字符数

    Returns:
        分块列表，每个元素包含 chunk_id, text, keywords
    """
    if not text or not text.strip():
        return []

    # 按段落分割
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = ""
    chunk_id = 0

    for para in paragraphs:
        # 如果当前块加上新段落不超过限制，则添加
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += ("\n\n" if current_chunk else "") + para
        else:
            # 保存当前块
            if current_chunk:
                keywords = extract_keywords(current_chunk)
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": current_chunk,
                    "keywords": keywords,
                })
                chunk_id += 1

            # 如果段落本身超过限制，需要进一步切分
            if len(para) > chunk_size:
                # 按句子切分
                sentences = re.split(r'[。！？.!?]', para)
                sentences = [s.strip() for s in sentences if s.strip()]

                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= chunk_size:
                        current_chunk += (" " if current_chunk else "") + sent
                    else:
                        if current_chunk:
                            keywords = extract_keywords(current_chunk)
                            chunks.append({
                                "chunk_id": chunk_id,
                                "text": current_chunk,
                                "keywords": keywords,
                            })
                            chunk_id += 1
                        current_chunk = sent
            else:
                current_chunk = para

    # 保存最后一块
    if current_chunk:
        keywords = extract_keywords(current_chunk)
        chunks.append({
            "chunk_id": chunk_id,
            "text": current_chunk,
            "keywords": keywords,
        })

    return chunks


def compute_tf(tokens: list[str]) -> dict[str, float]:
    """计算词频 (TF)"""
    if not tokens:
        return {}

    counter = Counter(tokens)
    total = len(tokens)
    return {word: count / total for word, count in counter.items()}


def compute_idf(doc_tokens_list: list[list[str]]) -> dict[str, float]:
    """计算逆文档频率 (IDF)"""
    if not doc_tokens_list:
        return {}

    num_docs = len(doc_tokens_list)
    doc_freq: Counter[str] = Counter()

    for tokens in doc_tokens_list:
        unique_tokens = set(tokens)
        for token in unique_tokens:
            doc_freq[token] += 1

    # 使用平滑的 IDF 公式: log((N + 1) / (df + 1)) + 1
    return {
        word: math.log((num_docs + 1) / (df + 1)) + 1
        for word, df in doc_freq.items()
    }


def compute_tfidf(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """计算 TF-IDF"""
    tf = compute_tf(tokens)
    return {
        word: tf_val * idf.get(word, 0)
        for word, tf_val in tf.items()
    }


def cosine_similarity(vec1: dict[str, float], vec2: dict[str, float]) -> float:
    """计算余弦相似度"""
    if not vec1 or not vec2:
        return 0.0

    # 获取所有词的集合
    all_words = set(vec1.keys()) | set(vec2.keys())

    # 计算点积和模
    dot_product = sum(vec1.get(w, 0) * vec2.get(w, 0) for w in all_words)
    norm1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
    norm2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)


class KnowledgeService:
    """知识库服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_document(
        self,
        doc_id: uuid.UUID,
        text: str,
    ) -> None:
        """
        处理上传的文档：分块并计算 TF-IDF

        Args:
            doc_id: 文档 ID
            text: 提取的文本内容
        """
        # 获取文档
        result = await self.db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return

        # 更新状态为处理中
        doc.embedding_status = EmbeddingStatus.PROCESSING
        await self.db.flush()

        try:
            # 分块
            chunks = chunk_text(text)
            doc.content_chunks = chunks

            # 计算 TF-IDF 数据
            # 收集所有分块的 tokens
            all_tokens = []
            chunk_tokens_list = []

            for chunk in chunks:
                tokens = tokenize(chunk["text"])
                tokens = remove_stop_words(tokens)
                chunk_tokens_list.append(tokens)
                all_tokens.extend(tokens)

            # 计算 IDF（基于所有分块）
            idf = compute_idf(chunk_tokens_list)

            # 计算每个分块的 TF-IDF
            chunk_tfidf = []
            for i, tokens in enumerate(chunk_tokens_list):
                tfidf = compute_tfidf(tokens, idf)
                chunk_tfidf.append({
                    "chunk_id": i,
                    "tfidf": tfidf,
                })

            # 存储 TF-IDF 数据
            doc.tfidf_data = {
                "idf": idf,
                "chunk_tfidf": chunk_tfidf,
            }

            doc.embedding_status = EmbeddingStatus.COMPLETED
            await self.db.flush()

        except Exception as e:
            doc.embedding_status = EmbeddingStatus.FAILED
            await self.db.flush()
            raise e

    async def search(
        self,
        query: str,
        doc_types: list[DocType] | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        搜索知识库

        Args:
            query: 搜索关键词
            doc_types: 限制文档类型
            limit: 返回结果数量限制

        Returns:
            搜索结果列表
        """
        # 构建查询
        stmt = select(KnowledgeDoc).where(
            KnowledgeDoc.embedding_status == EmbeddingStatus.COMPLETED
        )

        if doc_types:
            stmt = stmt.where(KnowledgeDoc.doc_type.in_(doc_types))

        result = await self.db.execute(stmt)
        docs = result.scalars().all()

        if not docs:
            return []

        # 处理查询
        query_tokens = tokenize(query)
        query_tokens = remove_stop_words(query_tokens)

        results = []

        for doc in docs:
            if not doc.tfidf_data or not doc.content_chunks:
                continue

            # 获取存储的 IDF
            idf = doc.tfidf_data.get("idf", {})
            chunk_tfidf_list = doc.tfidf_data.get("chunk_tfidf", [])

            # 计算查询的 TF-IDF
            query_tfidf = compute_tfidf(query_tokens, idf)

            # 与每个分块计算相似度
            for chunk_tfidf_item in chunk_tfidf_list:
                chunk_id = chunk_tfidf_item.get("chunk_id", 0)
                chunk_tfidf = chunk_tfidf_item.get("tfidf", {})

                # 计算余弦相似度
                score = cosine_similarity(query_tfidf, chunk_tfidf)

                if score > 0:
                    # 获取对应的文本
                    chunk_text = ""
                    for chunk in doc.content_chunks:
                        if chunk.get("chunk_id") == chunk_id:
                            chunk_text = chunk.get("text", "")
                            break

                    results.append({
                        "doc_id": doc.id,
                        "doc_name": doc.name,
                        "doc_type": doc.doc_type.value,
                        "chunk_id": chunk_id,
                        "text": chunk_text,
                        "score": score,
                    })

        # 按相似度排序，返回前 N 个结果
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
