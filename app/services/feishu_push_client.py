from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("webapi")


TOKEN_INVALID_CODES = {99991663, 99991664, 99991665}
TRANSIENT_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
MAX_CARD_BYTES = 28_000


class FeishuPushError(RuntimeError):
    pass


@dataclass
class FeishuPushConfig:
    app_id: str
    app_secret: str = field(repr=False)
    chat_id: str = field(repr=False)
    domain: str = "https://open.feishu.cn"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeishuPushConfig":
        domain = str(data.get("domain") or "https://open.feishu.cn").rstrip("/")
        return cls(
            app_id=str(data.get("app_id") or "").strip(),
            app_secret=str(data.get("app_secret") or "").strip(),
            chat_id=str(data.get("chat_id") or "").strip(),
            domain=domain or "https://open.feishu.cn",
        )

    def validate(self) -> None:
        missing = [
            name
            for name, value in {
                "app_id": self.app_id,
                "app_secret": self.app_secret,
                "chat_id": self.chat_id,
            }.items()
            if not value
        ]
        if missing:
            raise FeishuPushError(f"missing feishu config: {', '.join(missing)}")


class FeishuPushClient:
    """Small Feishu self-built app client inspired by cc-connect's Feishu sender."""

    def __init__(self, config: FeishuPushConfig, timeout: float = 20.0) -> None:
        config.validate()
        self.config = config
        self.timeout = timeout
        self._tenant_access_token: Optional[str] = None

    async def send_interactive_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        content = json.dumps(card, ensure_ascii=False)
        if len(content.encode("utf-8")) > MAX_CARD_BYTES:
            content = json.dumps(
                build_simple_card(
                    title="股票报告已生成",
                    markdown="报告内容较长，已发送精简卡片。请在系统报告页查看完整内容。",
                    template="blue",
                ),
                ensure_ascii=False,
            )
        return await self._send_message("interactive", content)

    async def send_text(self, text: str) -> Dict[str, Any]:
        content = json.dumps({"text": text}, ensure_ascii=False)
        return await self._send_message("text", content)

    async def _send_message(self, msg_type: str, content: str) -> Dict[str, Any]:
        await self._ensure_token()
        payload = {
            "receive_id": self.config.chat_id,
            "msg_type": msg_type,
            "content": content,
        }
        url = f"{self.config.domain}/open-apis/im/v1/messages"
        params = {"receive_id_type": "chat_id"}

        async def call() -> Dict[str, Any]:
            assert self._tenant_access_token
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    params=params,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._tenant_access_token}"},
                )
            return self._parse_response(response, "send feishu message")

        try:
            return await self._with_transient_retry(call)
        except FeishuPushError as exc:
            if not self._is_token_error(exc):
                raise
            logger.warning("Feishu token rejected, refreshing and retrying once")
            self._tenant_access_token = None
            await self._ensure_token()
            return await self._with_transient_retry(call)

    async def _ensure_token(self) -> None:
        if self._tenant_access_token:
            return
        url = f"{self.config.domain}/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.config.app_id, "app_secret": self.config.app_secret}

        async def call() -> Dict[str, Any]:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
            return self._parse_response(response, "fetch feishu tenant token")

        data = await self._with_transient_retry(call)
        token = str(data.get("tenant_access_token") or "").strip()
        if not token:
            raise FeishuPushError("feishu token response did not include tenant_access_token")
        self._tenant_access_token = token

    async def _with_transient_retry(self, fn, retries: int = 3) -> Dict[str, Any]:
        delay = 0.8
        last_error: Optional[Exception] = None
        for attempt in range(retries + 1):
            try:
                return await fn()
            except (httpx.TimeoutException, httpx.NetworkError, FeishuPushError) as exc:
                last_error = exc
                if isinstance(exc, FeishuPushError) and not self._is_transient_error(exc):
                    raise
                if attempt >= retries:
                    break
                await asyncio.sleep(delay)
                delay = min(delay * 2, 5)
        raise FeishuPushError(f"feishu request failed after retries: {_redact_text(str(last_error))}")

    def _parse_response(self, response: httpx.Response, operation: str) -> Dict[str, Any]:
        if response.status_code in TRANSIENT_STATUS_CODES:
            raise FeishuPushError(f"{operation} transient http status {response.status_code}")
        if response.status_code >= 400:
            raise FeishuPushError(
                f"{operation} http status {response.status_code}: {_redact_text(response.text[:300])}"
            )

        data = response.json()
        code = data.get("code", 0)
        if code != 0:
            message = data.get("msg") or data.get("message") or "unknown feishu error"
            raise FeishuPushError(f"{operation} code={code} msg={_redact_text(str(message))}")
        return data.get("data") or data

    def _is_token_error(self, exc: FeishuPushError) -> bool:
        text = str(exc)
        return any(str(code) in text for code in TOKEN_INVALID_CODES) or "token" in text.lower()

    def _is_transient_error(self, exc: FeishuPushError) -> bool:
        text = str(exc)
        return any(f"status {code}" in text for code in TRANSIENT_STATUS_CODES)


def build_simple_card(title: str, markdown: str, template: str = "blue") -> Dict[str, Any]:
    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": title[:80]},
        },
        "body": {
            "elements": [
                {
                    "tag": "markdown",
                    "content": preprocess_feishu_markdown(markdown),
                }
            ]
        },
    }


def preprocess_feishu_markdown(markdown: str) -> str:
    # Feishu renders fenced code more reliably when a fence starts on a new line.
    return str(markdown or "").replace("```", "\n```")


def _redact_text(text: str) -> str:
    redacted = str(text or "")
    sensitive_keys = ("app_secret", "tenant_access_token", "access_token", "chat_id", "Authorization")
    for key in sensitive_keys:
        redacted = re.sub(
            rf'("{re.escape(key)}"\s*:\s*")[^"]+(")',
            rf'\1***\2',
            redacted,
            flags=re.IGNORECASE,
        )
        redacted = re.sub(
            rf"({re.escape(key)}\s*[=:]\s*)[^\s,;]+",
            rf"\1***",
            redacted,
            flags=re.IGNORECASE,
        )
    return redacted
