from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def is_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def send_password_reset_email(email: str, reset_url: str) -> None:
    if not is_configured():
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = "Восстановление пароля — Накладная"
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = email
    message.set_content(
        "Вы запросили восстановление пароля.\n\n"
        f"Откройте ссылку в течение 30 минут:\n{reset_url}\n\n"
        "Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо."
    )

    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_ssl = os.getenv("SMTP_SSL", "false").lower() == "true"

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=15) as server:
        if not use_ssl and os.getenv("SMTP_STARTTLS", "true").lower() == "true":
            server.starttls()
        if username:
            server.login(username, password)
        server.send_message(message)
