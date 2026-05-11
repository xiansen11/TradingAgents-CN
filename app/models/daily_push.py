from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


A_STOCK_PATTERN = re.compile(r"^\d{6}$")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def normalize_stock_symbols(symbols: List[str]) -> List[str]:
    normalized: List[str] = []
    for raw in symbols:
        symbol = str(raw or "").strip()
        if not A_STOCK_PATTERN.fullmatch(symbol):
            raise ValueError("stock_symbols only supports 6 digit A-share codes")
        if symbol not in normalized:
            normalized.append(symbol)
    if not normalized:
        raise ValueError("stock_symbols must not be empty")
    return normalized


def validate_time_value(value: str) -> str:
    text = str(value or "").strip()
    if not TIME_PATTERN.fullmatch(text):
        raise ValueError("time must use HH:mm format")
    return text


class DailyPushAnalysisParameters(BaseModel):
    research_depth: str = "标准"
    selected_analysts: List[str] = Field(
        default_factory=lambda: ["market", "fundamentals", "news", "social"]
    )
    quick_analysis_model: Optional[str] = "qwen-turbo"
    deep_analysis_model: Optional[str] = "qwen-max"

    @field_validator("selected_analysts")
    @classmethod
    def validate_analysts(cls, value: List[str]) -> List[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if not cleaned:
            raise ValueError("selected_analysts must not be empty")
        return cleaned


class DailyPushFeishuConfig(BaseModel):
    app_id: str
    app_secret: str
    chat_id: str
    domain: Optional[str] = "https://open.feishu.cn"

    @field_validator("app_id", "app_secret", "chat_id")
    @classmethod
    def validate_required(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("field is required")
        return text

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: Optional[str]) -> str:
        text = str(value or "").strip()
        return text.rstrip("/") or "https://open.feishu.cn"


class DailyPushFeishuUpdate(BaseModel):
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    chat_id: Optional[str] = None
    domain: Optional[str] = None

    @field_validator("app_id", "app_secret", "chat_id", "domain")
    @classmethod
    def normalize_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class DailyPushSubscriptionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    enabled: bool = True
    stock_symbols: List[str]
    analysis_time: str = "18:00"
    push_time: str = "18:30"
    timezone: str = "Asia/Shanghai"
    analysis_parameters: DailyPushAnalysisParameters = Field(
        default_factory=DailyPushAnalysisParameters
    )
    feishu: DailyPushFeishuConfig

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("stock_symbols")
    @classmethod
    def validate_symbols(cls, value: List[str]) -> List[str]:
        return normalize_stock_symbols(value)

    @field_validator("analysis_time", "push_time")
    @classmethod
    def validate_times(cls, value: str) -> str:
        return validate_time_value(value)

    @field_validator("timezone")
    @classmethod
    def normalize_timezone(cls, value: str) -> str:
        text = str(value or "").strip()
        return text or "Asia/Shanghai"


class DailyPushSubscriptionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    enabled: Optional[bool] = None
    stock_symbols: Optional[List[str]] = None
    analysis_time: Optional[str] = None
    push_time: Optional[str] = None
    timezone: Optional[str] = None
    analysis_parameters: Optional[DailyPushAnalysisParameters] = None
    feishu: Optional[DailyPushFeishuUpdate] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return str(value or "").strip()

    @field_validator("stock_symbols")
    @classmethod
    def validate_symbols(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return None
        return normalize_stock_symbols(value)

    @field_validator("analysis_time", "push_time")
    @classmethod
    def validate_times(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return validate_time_value(value)


class DailyPushTestSendRequest(BaseModel):
    stock_symbol: Optional[str] = None

    @field_validator("stock_symbol")
    @classmethod
    def validate_symbol(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        return normalize_stock_symbols([value])[0]


class DailyPushRunListQuery(BaseModel):
    subscription_id: Optional[str] = None
    status: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class DailyPushRunStartResponse(BaseModel):
    run_id: str
    task_id: Optional[str] = None
    stock_symbol: str
    status: str


class DailyPushRunNowResponse(BaseModel):
    started: List[DailyPushRunStartResponse]
    skipped: List[Dict[str, Any]]
