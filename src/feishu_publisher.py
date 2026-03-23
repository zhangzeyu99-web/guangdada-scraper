"""Feishu (Lark) integration for guangdada scraper reports.

Two capabilities:

* **send_notification** — immediately usable; reuses the Feishu bot
  credentials already configured in ``openclaw.json``.
* **publish_report** — reserved interface that will create a Feishu
  document via the ``openclaw-lark`` plugin once it is available.
"""
from __future__ import annotations

import json
import logging
import ssl
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Candidate paths for openclaw.json (cross-platform)
_CONFIG_CANDIDATES = [
    Path("D:/project/openclaw/openclaw.json"),
    Path("/mnt/d/project/openclaw/openclaw.json"),
    Path.home() / ".openclaw" / "openclaw.json",
]


def _get_feishu_credentials() -> Optional[tuple[str, str, str]]:
    """Read Feishu bot credentials from openclaw.json.

    Returns ``(app_id, app_secret, target_open_id)`` or ``None``.
    """
    for candidate in _CONFIG_CANDIDATES:
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            channels = data.get("channels", {}).get("feishu", {})
            accounts = channels.get("accounts", {})
            bot = accounts.get("bot-xiaoxia", {})
            app_id = bot.get("appId", channels.get("appId", ""))
            app_secret = bot.get("appSecret", channels.get("appSecret", ""))
            allow_from = bot.get("groupAllowFrom", channels.get("groupAllowFrom", []))
            user_id = allow_from[0] if allow_from else ""
            if app_id and app_secret and user_id:
                return app_id, app_secret, user_id
        except (json.JSONDecodeError, OSError, IndexError):
            continue
    return None


def _get_tenant_token(app_id: str, app_secret: str) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        result = json.loads(resp.read())
    if result.get("code") != 0:
        raise RuntimeError(f"飞书 token 获取失败: {result}")
    return result["tenant_access_token"]


def _send_message(token: str, open_id: str, text: str) -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    body = json.dumps({
        "receive_id": open_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}),
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return json.loads(resp.read())


class FeishuPublisher:
    """Publish scrape results to Feishu."""

    def send_notification(self, summary: str) -> bool:
        """Send a plain-text notification via the Feishu bot.

        Returns ``True`` on success.
        """
        creds = _get_feishu_credentials()
        if not creds:
            logger.warning("未找到飞书凭据，跳过通知")
            return False

        app_id, app_secret, user_id = creds
        try:
            token = _get_tenant_token(app_id, app_secret)
            result = _send_message(token, user_id, summary)
            ok = result.get("code") == 0
            if ok:
                logger.info("飞书通知已发送")
            else:
                logger.warning("飞书通知发送失败: %s", result)
            return ok
        except Exception as exc:
            logger.error("飞书通知异常: %s", exc)
            return False

    def publish_report(self, report_md: str, title: str) -> str:
        """Publish the full Markdown report as a Feishu document.

        **Reserved interface** — will be implemented when the
        ``openclaw-lark`` plugin (``feishu_bitable_*`` tools) is
        integrated.  Currently raises ``NotImplementedError``.

        Parameters
        ----------
        report_md:
            Full Markdown content of the report.
        title:
            Document title.

        Returns
        -------
        str
            URL of the created Feishu document.
        """
        raise NotImplementedError(
            "飞书文档发布功能尚未实现。"
            "等待 openclaw-lark 插件集成后，此接口将自动启用。"
            "当前可使用 send_notification() 发送文字摘要。"
        )

    def publish_or_notify(self, report_md: str, title: str, mode: str = "notify") -> Optional[str]:
        """High-level dispatch based on *mode*.

        mode:
            ``"notify"`` — send a short text summary.
            ``"doc"``    — create a Feishu document (reserved).
            ``"both"``   — do both.

        Returns the document URL when available, otherwise ``None``.
        """
        doc_url: Optional[str] = None

        if mode in ("doc", "both"):
            try:
                doc_url = self.publish_report(report_md, title)
            except NotImplementedError as exc:
                logger.info("%s", exc)

        if mode in ("notify", "both"):
            preview = report_md[:500] + ("…" if len(report_md) > 500 else "")
            self.send_notification(f"📊 {title}\n\n{preview}")

        return doc_url
