from __future__ import annotations

from typing import Optional

import httpx
from zep_cloud.client import Zep

from ..config import Config


class ZepConnectivityError(RuntimeError):
    """Raised when the Zep client cannot establish a network connection."""


def build_zep_client(
    api_key: Optional[str] = None,
    *,
    trust_env: Optional[bool] = None,
    timeout: Optional[float] = None,
) -> Zep:
    resolved_api_key = api_key or Config.ZEP_API_KEY
    if not resolved_api_key:
        raise ValueError("ZEP_API_KEY 未配置")

    resolved_trust_env = Config.ZEP_TRUST_ENV if trust_env is None else trust_env
    resolved_timeout = Config.ZEP_TIMEOUT_SECONDS if timeout is None else timeout

    httpx_client = httpx.Client(
        timeout=resolved_timeout,
        follow_redirects=True,
        trust_env=resolved_trust_env,
    )
    return Zep(api_key=resolved_api_key, timeout=resolved_timeout, httpx_client=httpx_client)


def normalize_zep_exception(exc: Exception) -> Exception:
    if isinstance(exc, httpx.ConnectError):
        message = (
            "无法连接到 Zep 服务。当前默认不会继承系统代理环境变量；"
            "如果必须通过代理访问，请设置 ZEP_TRUST_ENV=true。"
        )
        detail = str(exc).strip()
        if detail:
            message = f"{message} 原始错误: {detail}"
        return ZepConnectivityError(message)
    return exc
