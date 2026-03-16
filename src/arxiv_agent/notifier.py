from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

import httpx

from .config import NotifyConfig
from .models import ScoredPaper, SummaryResult


class Notifier:
    def __init__(self, config: NotifyConfig) -> None:
        self.config = config

    def format_digest(self, items: list[tuple[ScoredPaper, SummaryResult]]) -> str:
        lines = ["arXiv 每日监控结果", ""]
        for idx, (scored, summary) in enumerate(items, start=1):
            p = scored.paper
            lines.extend(
                [
                    f"{idx}. [{scored.profile_name}] {p.title}",
                    f"   Score: {scored.score}",
                    f"   URL: {p.url}",
                    f"   摘要: {summary.summary_cn}",
                    f"   要点: {' | '.join(summary.highlights)}",
                    f"   建议: {summary.recommendation}",
                    "",
                ]
            )
        if len(lines) == 2:
            lines.append("今日无命中关键词的新论文。")
        return "\n".join(lines)

    def send(self, message: str) -> list[str]:
        sent_channels: list[str] = []

        if self.config.console:
            print(message)
            sent_channels.append("console")

        if self.config.email.enabled:
            self._send_email(message)
            sent_channels.append("email")

        if self.config.telegram.enabled:
            self._send_telegram(message)
            sent_channels.append("telegram")

        return sent_channels

    def _send_email(self, message: str) -> None:
        email_cfg = self.config.email
        password = os.getenv(email_cfg.password_env, "")
        if not all([email_cfg.smtp_host, email_cfg.username, email_cfg.from_addr, email_cfg.to_addrs, password]):
            raise ValueError("Email config incomplete or missing password env")

        msg = EmailMessage()
        msg["Subject"] = "arXiv Daily Digest"
        msg["From"] = email_cfg.from_addr
        msg["To"] = ", ".join(email_cfg.to_addrs)
        msg.set_content(message)

        with smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port) as server:
            if email_cfg.use_tls:
                server.starttls()
            server.login(email_cfg.username, password)
            server.send_message(msg)

    def _send_telegram(self, message: str) -> None:
        tg_cfg = self.config.telegram
        token = os.getenv(tg_cfg.bot_token_env, "")
        if not token or not tg_cfg.chat_id:
            raise ValueError("Telegram config incomplete or missing token env")

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": tg_cfg.chat_id, "text": message[:3900]}
        with httpx.Client(timeout=20) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
