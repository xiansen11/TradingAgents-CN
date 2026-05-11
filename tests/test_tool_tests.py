import asyncio

import pytest
from fastapi import HTTPException

from app.routers import tool_tests


def test_normalize_a_stock_code_rejects_invalid_code():
    with pytest.raises(HTTPException) as exc:
        tool_tests._normalize_a_stock_code("AAPL")

    assert exc.value.status_code == 400


def test_build_technical_summary_returns_indicators():
    items = [
        {
            "trade_date": f"202601{i:02d}",
            "open": 10 + i * 0.1,
            "high": 10.5 + i * 0.1,
            "low": 9.8 + i * 0.1,
            "close": 10.2 + i * 0.1,
            "volume": 1000 + i,
        }
        for i in range(1, 31)
    ]

    summary = tool_tests._build_technical_summary(items)

    assert summary["indicators"]
    assert "ma5" in summary["indicators"]
    assert "macd" in summary["indicators"]
    assert "rsi12" in summary["indicators"]


def test_jsonable_none_stays_safe_for_missing_mongo_docs():
    assert tool_tests._jsonable(None) is None
    quote = tool_tests._jsonable(None) or {}

    assert quote.get("close") is None


def test_timed_call_marks_mcp_error_result_as_error():
    result = tool_tests._make_diagnostic("mcp", "news", "error", 0, "boom")

    async_result = asyncio.run(tool_tests._timed_call(
        "mcp",
        "news",
        lambda: type("MCPResult", (), {"ok": False, "error": "boom"})(),
        include_raw=True,
        timeout_seconds=1,
    ))

    assert result["status"] == "error"
    assert async_result["status"] == "error"
    assert async_result["message"] == "boom"


def test_timed_call_can_mark_empty_result_as_unsupported():
    result = asyncio.run(tool_tests._timed_call(
        "baostock",
        "quote",
        lambda: None,
        include_raw=False,
        timeout_seconds=1,
        empty_status="unsupported",
        empty_message="not implemented",
    ))

    assert result["status"] == "unsupported"
    assert result["message"] == "not implemented"


def test_adapter_unavailable_modules_are_skipped(monkeypatch):
    class FakeManager:
        def __init__(self):
            self.adapters = [FakeAdapter()]

    class FakeAdapter:
        name = "tushare"

        def is_available(self):
            return False

        def get_token_source(self):
            return "database"

    monkeypatch.setattr("app.services.data_sources.manager.DataSourceManager", FakeManager)

    diagnostics = asyncio.run(tool_tests._run_adapter_tests(
        "000001",
        include_raw=False,
        timeout_seconds=1,
        modules={"quote", "technical"},
    ))

    assert diagnostics[0]["status"] == "error"
    assert {item["status"] for item in diagnostics[1:]} == {"skipped"}


def test_mcp_import_failure_returns_diagnostic(monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "tradingagents.dataflows.mcp.gateway":
            raise ImportError("missing mcp gateway")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    diagnostics = asyncio.run(tool_tests._run_mcp_tests("000001", include_raw=False, timeout_seconds=1))

    assert diagnostics
    assert diagnostics[0]["status"] == "error"
