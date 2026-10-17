"""Telegram AI bot with optional MySQL persistence and read-only GitHub commands."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
import pymysql
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from github_integration import register_github_handlers

load_dotenv()
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
)
logger = logging.getLogger("telegram_ai_bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
OPENAI_API_URL = "https://api.openai.com/v1/responses"
SYSTEM_PROMPT = os.getenv(
    "AI_SYSTEM_PROMPT",
    "You are a helpful, clear, and accurate assistant. Reply in the user's language. "
    "Do not claim to have access to accounts, files, or live data unless a connected tool actually provides it.",
)
MAX_HISTORY = 12
MAX_TELEGRAM_MESSAGE = 3900
DB_ENABLED = os.getenv("MYSQL_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
def _parse_ids(value: str) -> set[int]:
    ids: set[int] = set()
    for token in value.split(","):
        token = token.strip()
        if token.isdigit() and int(token) > 0:
            ids.add(int(token))
    return ids


BOT_ALLOWED_IDS = _parse_ids(os.getenv("BOT_ALLOWED_TELEGRAM_IDS", ""))
ADMIN_IDS = _parse_ids(os.getenv("ADMIN_ID", "")) | _parse_ids(
    os.getenv("GITHUB_ALLOWED_TELEGRAM_IDS", "")
)


def is_authorized(update: Update) -> bool:
    user = update.effective_user
    return bool(user and (not BOT_ALLOWED_IDS or user.id in BOT_ALLOWED_IDS))


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id in ADMIN_IDS)


def _db_connect():
    if not DB_ENABLED:
        return None
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "telegram_ai"),
        charset="utf8mb4",
        connect_timeout=4,
        read_timeout=5,
        write_timeout=5,
        autocommit=True,
    )


def _db_ensure_user(telegram_id: int, username: str | None, admin: bool) -> None:
    if not DB_ENABLED:
        return
    with _db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (telegram_id, username, is_admin)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    username = VALUES(username),
                    is_admin = GREATEST(is_admin, VALUES(is_admin))
                """,
                (telegram_id, username, int(admin)),
            )


def _db_save_message(telegram_id: int, role: str, message: str) -> None:
    if not DB_ENABLED:
        return
    with _db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chat_history (telegram_id, role, message) VALUES (%s, %s, %s)",
                (telegram_id, role, message),
            )


def _db_get_history(telegram_id: int) -> list[dict[str, str]]:
    if not DB_ENABLED:
        return []
    with _db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT role, message FROM chat_history WHERE telegram_id = %s ORDER BY id DESC LIMIT %s",
                (telegram_id, MAX_HISTORY),
            )
            rows = cursor.fetchall()
    return [{"role": role, "content": message} for role, message in reversed(rows)]


def _db_clear_history(telegram_id: int) -> None:
    if not DB_ENABLED:
        return
    with _db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM chat_history WHERE telegram_id = %s", (telegram_id,))


def _db_update_ai_setting(enabled: bool) -> None:
    if not DB_ENABLED:
        return
    with _db_connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO bot_settings (setting_key, setting_value) VALUES ('ai_enabled', %s) "
                "ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)",
                ("1" if enabled else "0",),
            )


async def _db_call(function, *args):
    if not DB_ENABLED:
        return None
    try:
        return await asyncio.to_thread(function, *args)
    except Exception:
        logger.exception("MySQL operation failed. Check MYSQL_* settings and import the SQL schema.")
        return None


async def _authorized_or_reply(update: Update) -> bool:
    if is_authorized(update):
        return True
    if update.effective_message:
        await update.effective_message.reply_text(
            "Bot ini dibatasi untuk ID Telegram yang diizinkan. Minta admin memeriksa BOT_ALLOWED_TELEGRAM_IDS."
        )
    return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_reply(update):
        return
    user = update.effective_user
    if user:
        await _db_call(_db_ensure_user, user.id, user.username, is_admin(update))
    context.bot_data.setdefault("ai_enabled", os.getenv("AI_ENABLED", "1").lower() not in {"0", "false", "off"})
    await update.effective_message.reply_text(
        "Halo! Aku bot AI yang terhubung ke GitHub.\n\n"
        "Kirim pesan untuk ngobrol dengan AI.\n"
        "Ketik /help untuk daftar perintah.\n\n"
        "Contoh GitHub:\n"
        "/github — cek koneksi GitHub\n"
        "/ghrepo petrych0re/ggg — detail repository\n"
        "/ghcommits petrych0re/ggg — commit terbaru"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_reply(update):
        return
    await update.effective_message.reply_text(
        "PERINTAH BOT\n"
        "/start — mulai bot\n"
        "/help — tampilkan bantuan\n"
        "/status — status AI dan database\n"
        "/reset — hapus riwayat chat milikmu\n"
        "/ai_on — aktifkan AI (admin)\n"
        "/ai_off — nonaktifkan AI (admin)\n\n"
        "PERINTAH GITHUB (baca-saja)\n"
        "/github — cek koneksi akun GitHub\n"
        "/ghrepos [halaman] — daftar repository\n"
        "/ghrepo owner/repo — detail repository\n"
        "/ghissues owner/repo — issue terbuka\n"
        "/ghcommits owner/repo — commit terbaru\n"
        "/ghfile owner/repo path/file.py — preview file"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_reply(update):
        return
    enabled = context.bot_data.setdefault(
        "ai_enabled", os.getenv("AI_ENABLED", "1").lower() not in {"0", "false", "off"}
    )
    await update.effective_message.reply_text(
        "AI: " + ("aktif" if enabled else "nonaktif") + "\n"
        "OpenAI API key: " + ("terpasang" if OPENAI_API_KEY else "belum diatur") + "\n"
        "MySQL: " + ("dikonfigurasi" if DB_ENABLED else "nonaktif (memori sementara)") + "\n"
        "GitHub token: " + ("terpasang" if os.getenv("GITHUB_TOKEN", "").strip() else "belum diatur")
    )


async def ai_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_reply(update):
        return
    if not is_admin(update):
        await update.effective_message.reply_text("Perintah ini khusus admin.")
        return
    context.bot_data["ai_enabled"] = True
    await _db_call(_db_update_ai_setting, True)
    await update.effective_message.reply_text("AI diaktifkan.")


async def ai_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_reply(update):
        return
    if not is_admin(update):
        await update.effective_message.reply_text("Perintah ini khusus admin.")
        return
    context.bot_data["ai_enabled"] = False
    await _db_call(_db_update_ai_setting, False)
    await update.effective_message.reply_text("AI dinonaktifkan.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_reply(update):
        return
    user = update.effective_user
    if not user:
        return
    context.user_data["history"] = []
    await _db_call(_db_clear_history, user.id)
    await update.effective_message.reply_text("Riwayat chat milikmu sudah dihapus.")


async def _call_openai(history: list[dict[str, str]]) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY belum diatur di file .env.")
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": OPENAI_MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": history,
        "max_output_tokens": 900,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
            response = await client.post(OPENAI_API_URL, headers=headers, json=payload)
    except httpx.TimeoutException:
        raise RuntimeError("Layanan AI kehabisan waktu untuk menjawab. Coba lagi.") from None
    except httpx.RequestError:
        raise RuntimeError("Gagal terhubung ke layanan AI. Periksa koneksi internet.") from None

    if response.status_code == 401:
        raise RuntimeError("OPENAI_API_KEY ditolak. Periksa key di file .env.")
    if response.status_code == 429:
        raise RuntimeError("Batas penggunaan API tercapai atau saldo API tidak mencukupi. Periksa dashboard penyedia API.")
    if response.status_code >= 500:
        raise RuntimeError("Layanan AI sedang bermasalah. Coba lagi nanti.")
    if not response.is_success:
        try:
            message = response.json().get("error", {}).get("message", "")
        except ValueError:
            message = ""
        logger.warning("OpenAI API returned HTTP %s", response.status_code)
        raise RuntimeError(message[:240] if message else f"Permintaan AI gagal (HTTP {response.status_code}).")

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("Layanan AI mengembalikan respons yang tidak valid.") from None

    parts: list[str] = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                parts.append(block["text"])
    answer = "\n".join(part for part in parts if part.strip()).strip()
    if not answer:
        raise RuntimeError("AI tidak mengembalikan teks. Coba kirim pesan lain.")
    return answer


async def _send_long_message(update: Update, text: str) -> None:
    message = update.effective_message
    if not message:
        return
    for start in range(0, len(text), MAX_TELEGRAM_MESSAGE):
        await message.reply_text(text[start : start + MAX_TELEGRAM_MESSAGE])


async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized_or_reply(update):
        return
    message = update.effective_message
    user = update.effective_user
    if not message or not message.text or not user:
        return
    enabled = context.bot_data.setdefault(
        "ai_enabled", os.getenv("AI_ENABLED", "1").lower() not in {"0", "false", "off"}
    )
    if not enabled:
        await message.reply_text("AI sedang nonaktif. Minta admin menjalankan /ai_on.")
        return

    prompt = message.text.strip()
    if not prompt:
        return
    if len(prompt) > 8000:
        await message.reply_text("Pesan terlalu panjang. Batas pesan AI adalah 8.000 karakter.")
        return

    await _db_call(_db_ensure_user, user.id, user.username, is_admin(update))
    await _db_call(_db_save_message, user.id, "user", prompt)
    history: list[dict[str, str]] = []
    if DB_ENABLED:
        fetched = await _db_call(_db_get_history, user.id)
        if fetched:
            history = fetched
    if not history:
        local_history = context.user_data.setdefault("history", [])
        local_history.append({"role": "user", "content": prompt})
        history = local_history[-MAX_HISTORY:]
    else:
        context.user_data["history"] = history[-MAX_HISTORY:]

    try:
        await message.chat.send_action("typing")
        answer = await _call_openai(history)
    except RuntimeError as exc:
        await message.reply_text(str(exc))
        return
    except Exception:
        logger.exception("Unexpected AI handler failure")
        await message.reply_text("Terjadi kesalahan saat memproses pesan.")
        return

    await _db_call(_db_save_message, user.id, "assistant", answer)
    local_history = context.user_data.setdefault("history", [])
    if not DB_ENABLED:
        local_history.append({"role": "assistant", "content": answer})
        context.user_data["history"] = local_history[-MAX_HISTORY:]
    else:
        context.user_data["history"] = (history + [{"role": "assistant", "content": answer}])[-MAX_HISTORY:]
    await _send_long_message(update, answer)


async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Mulai bot"),
        BotCommand("help", "Bantuan perintah"),
        BotCommand("status", "Status AI, MySQL, dan GitHub"),
        BotCommand("reset", "Hapus riwayat chat"),
        BotCommand("ai_on", "Aktifkan AI (admin)"),
        BotCommand("ai_off", "Nonaktifkan AI (admin)"),
        BotCommand("github", "Cek koneksi GitHub"),
        BotCommand("ghrepos", "Daftar repository GitHub"),
        BotCommand("ghrepo", "Detail repository GitHub"),
        BotCommand("ghissues", "Issue terbuka GitHub"),
        BotCommand("ghcommits", "Commit terbaru GitHub"),
        BotCommand("ghfile", "Baca preview file GitHub"),
    ]
    await application.bot.set_my_commands(commands)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN belum diatur di file .env.")
    if DB_ENABLED and not os.getenv("MYSQL_DATABASE", "telegram_ai").strip():
        raise SystemExit("MYSQL_DATABASE kosong. Periksa file .env.")
    if DB_ENABLED:
        logger.info("MySQL persistence enabled.")
    else:
        logger.warning("MySQL disabled; chat history is stored only in process memory.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    application.bot_data["ai_enabled"] = os.getenv("AI_ENABLED", "1").lower() not in {"0", "false", "off"}
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(CommandHandler("ai_on", ai_on_command))
    application.add_handler(CommandHandler("ai_off", ai_off_command))
    register_github_handlers(application)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message))
    logger.info("Telegram AI bot is starting.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
