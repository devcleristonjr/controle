from __future__ import annotations

import smtplib
from email.message import EmailMessage

from flask import current_app


def enviar_email(destinatario: str, assunto: str, corpo: str) -> None:
    server = current_app.config.get("MAIL_SERVER")
    port = int(current_app.config.get("MAIL_PORT", 587))
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    sender = current_app.config.get("MAIL_DEFAULT_SENDER")
    use_tls = current_app.config.get("MAIL_USE_TLS", True)

    if not server or not sender:
        raise RuntimeError("Configuração de e-mail incompleta. Defina MAIL_SERVER e MAIL_DEFAULT_SENDER.")

    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = sender
    mensagem["To"] = destinatario
    mensagem.set_content(corpo)

    with smtplib.SMTP(server, port, timeout=20) as smtp:
        smtp.ehlo()
        if use_tls:
            smtp.starttls()
            smtp.ehlo()
        if username:
            smtp.login(username, password or "")
        smtp.send_message(mensagem)
