"""数据模型定义"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ConfigRequest(BaseModel):
    """OpenAI配置请求"""
    model_config = {"protected_namespaces": ()}
    
    api_key: str = Field(..., description="OpenAI API密钥")
    base_url: Optional[str] = Field(None, description="Base URL")
    model_name: str = Field("gpt-3.5-turbo", description="模型名称")


class ConfigResponse(BaseModel):
    """配置响应"""
    success: bool
    message: str


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: List[str] = []
    providers: List["ProviderModelOption"] = []
    default_provider_config_id: Optional[str] = None
    success: bool
    message: str = ""


class ProviderModelOption(BaseModel):
    """单个 provider 的可用模型列表"""
    config_id: str
    provider: str
    models: List[str]
    default_model: str
    is_default: bool = False


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    success: bool
    message: str
    file_content: Optional[str] = None
    old_outline: Optional[str] = None


class AnalysisType(str, Enum):
    """分析类型"""
    OVERVIEW = "overview"
    REQUIREMENTS = "requirements"


class AnalysisRequest(BaseModel):
    """文档分析请求"""
    file_content: str = Field(..., description="文档内容")
    analysis_type: AnalysisType = Field(..., description="分析类型")
    model_name: Optional[str] = Field(None, description="可选的模型名称，覆盖默认配置")
    provider_config_id: Optional[str] = Field(None, description="可选的 Provider 配置 ID，覆盖默认配置")


class OutlineItem(BaseModel):
    """目录项"""
    id: str
    title: str
    description: str
    children: Optional[List['OutlineItem']] = None
    content: Optional[str] = None


# 解决循环引用
OutlineItem.model_rebuild()


class OutlineResponse(BaseModel):
    """目录响应"""
    outline: List[OutlineItem]


class OutlineRequest(BaseModel):
    """目录生成请求"""
    overview: str = Field(..., description="项目概述")
    requirements: str = Field(..., description="技术评分要求")
    uploaded_expand: Optional[bool] = Field(False, description="是否已上传方案扩写文件")
    old_outline: Optional[str] = Field(None, description="上传的方案扩写文件解析出的旧目录JSON")
    old_document: Optional[str] = Field(None, description="上传的方案扩写文件解析出的旧文档")
    model_name: Optional[str] = Field(None, description="可选的模型名称，覆盖默认配置")
    provider_config_id: Optional[str] = Field(None, description="可选的 Provider 配置 ID，覆盖默认配置")

class ContentGenerationRequest(BaseModel):
    """内容生成请求"""
    outline: Dict[str, Any] = Field(..., description="目录结构")
    project_overview: str = Field("", description="项目概述")


class ChapterContentRequest(BaseModel):
    """单章节内容生成请求"""
    chapter: Dict[str, Any] = Field(..., description="章节信息")
    parent_chapters: Optional[List[Dict[str, Any]]] = Field(None, description="上级章节列表")
    sibling_chapters: Optional[List[Dict[str, Any]]] = Field(None, description="同级章节列表")
    project_overview: str = Field("", description="项目概述")
    model_name: Optional[str] = Field(None, description="可选的模型名称，覆盖默认配置")
    provider_config_id: Optional[str] = Field(None, description="可选的 Provider 配置 ID，覆盖默认配置")


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None


class WordExportRequest(BaseModel):
    """Word导出请求"""
    project_name: Optional[str] = Field(None, description="项目名称")
    project_overview: Optional[str] = Field(None, description="项目概述")
    outline: List[OutlineItem] = Field(..., description="目录结构，包含内容")


# ============ 项目上下文相关 Schema ============

class ProjectFileUploadResponse(BaseModel):
    """项目文件上传响应"""
    success: bool
    message: str
    project_id: str
    file_content_length: int = Field(..., description="文件内容字符数")


class ProjectAnalysisRequest(BaseModel):
    """基于项目的文档分析请求"""
    project_id: str = Field(..., description="项目ID")
    analysis_type: AnalysisType = Field(..., description="分析类型")
    model_name: Optional[str] = Field(None, description="可选的模型名称，覆盖默认配置")
    provider_config_id: Optional[str] = Field(None, description="可选的 Provider 配置 ID，覆盖默认配置")


# ============ 项目上下文版本的目录和内容生成 Schema ============

class ProjectOutlineRequest(BaseModel):
    """基于项目的目录生成请求"""
    project_id: str = Field(..., description="项目ID")
    model_name: Optional[str] = Field(None, description="可选的模型名称，覆盖默认配置")
    provider_config_id: Optional[str] = Field(None, description="可选的 Provider 配置 ID，覆盖默认配置")
    outline_data: Optional[Dict[str, Any]] = Field(None, description="可选的目录数据，用于兜底（当数据库中没有数据时使用前端数据）")


class ProjectContentGenerateRequest(BaseModel):
    """基于项目的章节内容生成请求"""
    project_id: str = Field(..., description="项目ID")
    chapter_id: str = Field(..., description="章节ID")
    model_name: Optional[str] = Field(None, description="可选的模型名称，覆盖默认配置")
    provider_config_id: Optional[str] = Field(None, description="可选的 Provider 配置 ID，覆盖默认配置")


class ChapterCreatedResponse(BaseModel):
    """章节创建响应"""
    id: str
    chapter_number: str
    title: str
    parent_id: Optional[str] = None
    status: str = "pending"


class ProjectOutlineResponse(BaseModel):
    """项目目录生成响应"""
    project_id: str
    chapters: List[ChapterCreatedResponse]
    total_count: int


# ============ 知识库相关 Schema ============

class KnowledgeDocType(str, Enum):
    """知识库文档类型"""
    HISTORY_BID = "history_bid"      # 历史标书
    COMPANY_INFO = "company_info"    # 企业资料
    CASE_FRAGMENT = "case_fragment"  # 案例片段
    OTHER = "other"                  # 其他


class KnowledgeScope(str, Enum):
    """知识库范围"""
    GLOBAL = "global"          # 全局
    ENTERPRISE = "enterprise"  # 企业私有
    USER = "user"              # 用户私有


class KnowledgeContentSource(str, Enum):
    """知识库内容来源"""
    FILE = "file"      # 文件上传
    MANUAL = "manual"  # 手动输入


class KnowledgeDocCreate(BaseModel):
    """创建知识库文档请求"""
    title: str = Field(..., description="标题")
    doc_type: KnowledgeDocType = Field(..., description="文档类型")
    scope: KnowledgeScope = Field(..., description="数据范围")
    content_source: KnowledgeContentSource = Field(..., description="内容来源")
    content: Optional[str] = Field(None, description="手动输入的内容（content_source=manual 时必填）")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签列表")
    keywords: Optional[List[str]] = Field(default_factory=list, description="关键词列表")
    category: Optional[str] = Field(None, description="分类")


class KnowledgeDocUpdate(BaseModel):
    """更新知识库文档请求"""
    title: Optional[str] = Field(None, description="标题")
    doc_type: Optional[KnowledgeDocType] = Field(None, description="文档类型")
    scope: Optional[KnowledgeScope] = Field(None, description="数据范围")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")
    category: Optional[str] = Field(None, description="分类")


class KnowledgeDocResponse(BaseModel):
    """知识库文档响应"""
    id: str
    title: str
    doc_type: str
    scope: str
    owner_id: Optional[str] = None
    content_source: str
    file_type: Optional[str] = None
    pageindex_status: str
    pageindex_error: Optional[str] = None
    tags: List[str] = []
    keywords: List[str] = []
    category: Optional[str] = None
    usage_count: int = 0
    last_used_at: Optional[str] = None
    created_at: str
    updated_at: str


class KnowledgeSearchRequest(BaseModel):
    """知识库检索请求"""
    chapter_title: str = Field(..., description="章节标题")
    chapter_description: Optional[str] = Field("", description="章节描述")
    parent_chapters: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="上级章节信息")
    project_overview: str = Field(..., description="项目概述")
    top_k: int = Field(5, description="返回前K个最相关的结果")


class KnowledgeSearchResult(BaseModel):
    """知识库检索结果"""
    id: str
    title: str
    doc_type: str
    relevance_score: float = Field(..., description="相关性得分（0-1）")
    matched_nodes: List[Dict[str, Any]] = Field(default_factory=list, description="匹配的树节点")
    content_preview: str = Field(..., description="内容预览")


class KnowledgeSearchResponse(BaseModel):
    """知识库检索响应"""
    results: List[KnowledgeSearchResult]
    total: int


class ContentGenerateWithKnowledgeRequest(BaseModel):
    """带知识库的内容生成请求"""
    project_id: str = Field(..., description="项目ID")
    chapter_id: str = Field(..., description="章节ID")
    knowledge_ids: List[str] = Field(default_factory=list, description="选中的知识库ID列表")
    model_name: Optional[str] = Field(None, description="可选的模型名称，覆盖默认配置")
