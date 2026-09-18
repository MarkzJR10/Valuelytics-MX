from __future__ import annotations

import logging
import requests

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def send_ev_alert(
    match: str,
    market: str,
    selection: str,
    rec_odd: float,
    fair_odd: float,
    ev_pct: float,
    bookmaker: str = "Playdoit",
    bot_token: str = TELEGRAM_BOT_TOKEN,
    chat_id: str = TELEGRAM_CHAT_ID,
) -> bool:
    """
    Envía una alerta de apuesta con Valor Esperado (+EV) a un canal o chat de Telegram en formato HTML.

    Args:
        match (str): Nombre del partido/evento (ej. "América vs Chivas").
        market (str): Nombre del mercado (ej. "Both Teams to Score").
        selection (str): Selección (ej. "Yes" u "Over 2.5").
        rec_odd (float): Cuota ofrecida por la casa recreativa.
        fair_odd (float): Cuota justa calculada (1 / fair_prob).
        ev_pct (float): Porcentaje de EV (ej. 5.5 para 5.5% EV).
        bookmaker (str): Nombre de la casa recreativa. Por defecto "Playdoit".
        bot_token (str): Token del Bot de Telegram.
        chat_id (str): ID del canal o chat de Telegram.

    Returns:
        bool: True si la alerta se envió exitosamente, False en caso contrario.
    """
    if not bot_token or not chat_id:
        logger.warning(
            "Telegram Bot Token o Chat ID no configurados. Omite el envío de la alerta."
        )
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    message_html = (
        f"🚨 <b>¡OPORTUNIDAD DE VALOR (+EV)!</b> 🚨\n\n"
        f"⚽ <b>Partido:</b> {match}\n"
        f"📊 <b>Mercado:</b> {market}\n"
        f"🎯 <b>Selección:</b> <code>{selection}</code>\n\n"
        f"🟢 <b>Casa Recreativa ({bookmaker}):</b> <code>{rec_odd:.2f}</code>\n"
        f"⚖️ <b>Cuota Justa Sharp:</b> <code>{fair_odd:.2f}</code>\n"
        f"📈 <b>Valor Esperado (EV):</b> <b>+{ev_pct:.2f}%</b>\n\n"
        f"🤖 <i>Valuelytics MX - Scanner Automatizado</i>"
    )

    payload = {
        "chat_id": chat_id,
        "text": message_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("ok"):
            logger.info(f"Alerta enviada con éxito para {match} - {selection}")
            return True
        else:
            logger.error(f"Telegram API devolvió error: {data.get('description')}")
            return False

    except Exception as e:
        logger.error(f"Excepción al enviar mensaje a Telegram: {e}")
        return False
