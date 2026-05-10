from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from .user import PyObjectId
from app.utils.timezone import now_tz


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisParameters(BaseModel):
    market_type: str = "A股"
    analysis_date: Optional[datetime] = None
    research_depth: str = "标准"
    selected_analysts: List[str] = Field(default_factory=lambda: ["market", "fundamentals", "news", "social"])
    custom_prompt: Optional[str] = None
    include_sentiment: bool = True
    include_risk: bool = True
    language: str = "zh-CN"
    quick_analysis_model: Optional[str] = "qwen-turbo"
    deep_analysis_model: Optional[str] = "qwen-max"


class AnalysisResult(BaseModel):
    analysis_id: Optional[str] = None
    summary: Optional[str] = None
    recommendation: Optional[str] = None
    confidence_score: Optional[float] = None
    risk_level: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    detailed_analysis: Optional[Dict[str, Any]] = None
    reports: Dict[str, Any] = Field(default_factory=dict)
    charts: List[str] = Field(default_factory=list)
    tokens_used: int = 0
    execution_time: float = 0.0
    error_message: Optional[str] = None
    model_info: Optional[str] = None


class AnalysisTask(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    task_id: str = Field(..., description="任务唯一标识")
    user_id: PyObjectId
    symbol: str = Field(..., description="6位A股代码")
    stock_code: Optional[str] = Field(None, description="兼容字段，优先使用symbol")
    stock_name: Optional[str] = None
    status: AnalysisStatus = AnalysisStatus.PENDING
    progress: int = Field(default=0, ge=0, le=100)
    created_at: datetime = Field(default_factory=now_tz)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    worker_id: Optional[str] = None
    parameters: AnalysisParameters = Field(default_factory=AnalysisParameters)
    result: Optional[AnalysisResult] = None
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class StockInfo(BaseModel):
    symbol: str = Field(..., description="6位A股代码")
    code: Optional[str] = Field(None, description="兼容字段，优先使用symbol")
    name: str
    market: str = "A股"
    industry: Optional[str] = None
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    price: Optional[float] = None
    change_percent: Optional[float] = None


class SingleAnalysisRequest(BaseModel):
    symbol: Optional[str] = Field(None, description="6位A股代码")
    stock_code: Optional[str] = Field(None, description="兼容字段，优先使用symbol")
    parameters: Optional[AnalysisParameters] = None

    def get_symbol(self) -> str:
        return self.symbol or self.stock_code or ""


class AnalysisTaskResponse(BaseModel):
    task_id: str
    symbol: str
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None
    status: AnalysisStatus
    progress: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result: Optional[AnalysisResult]

    @field_serializer("created_at", "started_at", "completed_at")
    def serialize_datetime(self, value: Optional[datetime], _info) -> Optional[str]:
        return value.isoformat() if value else None


class AnalysisHistoryQuery(BaseModel):
    status: Optional[AnalysisStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    symbol: Optional[str] = None
    stock_code: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    def get_symbol(self) -> Optional[str]:
        return self.symbol or self.stock_code
