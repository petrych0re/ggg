"""Read-only GitHub commands for a python-telegram-bot v20+ application.

Configure GITHUB_TOKEN and GITHUB_ALLOWED_TELEGRAM_IDS (or ADMIN_ID) in the
bot's local environment. This module never writes to GitHub.
"""
from __future__ import annotations

import base64
import html
import os
import re
from typing import Any
from urllib.parse import quote

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_REPO_PART = re.compile(r"^[A-Za-z0-9_.-]+$")


class GitHubAPIError(Exception):
    """A safe-to-display GitHub API error."""


def _allowed_telegram_ids() -> set[int]:
    raw = os.getenv("GITHUB_ALLOWED_TELEGRAM_IDS", "").strip()
    if not raw:
        raw = os.getenv("ADMIN_ID", "").strip()
    result: set[int] = set()
    for value in raw.split(","):
        value = value.strip()
        if value.isdigit() and int(value) > 0:
            result.add(int(value))
    return result


async def _is_authorized(update: Update) -> bool:
    message = update.effective_message
    user = update.effective_user
    allowed = _allowed_telegram_ids()
    if user and user.id in allowed:
        return True
    if message:
        if not allowed:
            await message.reply_text(
                "Fitur GitHub belum dikonfigurasi. Admin perlu mengisi "
                "GITHUB_ALLOWED_TELEGRAM_IDS di file .env."
            )
        else:
            await message.reply_text("Akses ditolak: perintah GitHub hanya untuk admin yang diizinkan.")
    return False


def _token() -> str:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise GitHubAPIError(
            "GITHUB_TOKEN belum diatur di file .env. Gunakan token GitHub dengan izin baca minimum yang diperlukan."
        )
    return token


async def _get(endpoint: str, params: dict[str, Any] | None = None) -> Any:
    token = _token()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": _API_VERSION,
        "User-Agent": "Telegram-GitHub-ReadOnly-Integration",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            response = await client.get(f"{_API_ROOT}{endpoint}", headers=headers, params=params)
    except httpx.RequestError:
        raise GitHubAPIError("Gagal menghubungi GitHub. Periksa koneksi internet lalu coba lagi.") from None

    if response.status_code == 401:
        raise GitHubAPIError("GITHUB_TOKEN ditolak atau kedaluwarsa. Periksa token di file .env.")
    if response.status_code == 403:
        if response.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubAPIError("Batas permintaan GitHub API tercapai. Coba lagi setelah reset.")
        raise GitHubAPIError("GitHub menolak permintaan. Periksa izin token dan akses repository.")
    if response.status_code == 404:
        raise GitHubAPIError("Data tidak ditemukan atau repository tidak bisa diakses oleh token ini.")
    if response.status_code >= 500:
        raise GitHubAPIError("Layanan GitHub sedang bermasalah. Coba lagi nanti.")
    if not response.is_success:
        raise GitHubAPIError(f"Permintaan GitHub gagal (HTTP {response.status_code}).")
    try:
        return response.json()
    except ValueError:
        raise GitHubAPIError("GitHub mengembalikan respons yang tidak bisa dibaca.") from None


def _repo_name(value: str) -> str:
    parts = value.split("/")
    if len(parts) != 2 or not all(_REPO_PART.fullmatch(part) for part in parts):
        raise GitHubAPIError("Format repository harus owner/repo, contoh: octocat/Hello-World.")
    if parts[0] in {".", ".."} or parts[1] in {".", ".."}:
        raise GitHubAPIError("Nama repository tidak valid.")
    return f"{parts[0]}/{parts[1]}"


async def _handle_error(update: Update, error: Exception) -> None:
    message = update.effective_message
    if message:
        text = error.args[0] if isinstance(error, GitHubAPIError) and error.args else "Terjadi kesalahan saat mengakses GitHub."
        await message.reply_text(html.escape(str(text)))


async def github_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_authorized(update):
        return
    try:
        profile = await _get("/user")
        text = (
            "✅ <b>GitHub terhubung</b>\n"
            f"Akun: <a href=\"{html.escape(profile.get('html_url', 'https://github.com'), quote=True)}\">"
            f"{html.escape(profile.get('login', 'unknown'))}</a>\n"
            f"Nama: {html.escape(profile.get('name') or '—')}\n"
            f"Repository publik: {profile.get('public_repos', 0)}\n\n"
            "<b>Perintah:</b>\n"
            "/ghrepos [halaman] — repository akun yang terhubung\n"
            "/ghrepo owner/repo — detail repository\n"
            "/ghissues owner/repo — issue terbuka\n"
            "/ghcommits owner/repo — commit terbaru\n"
            "/ghfile owner/repo path/file — baca file teks"
        )
        await update.effective_message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        await _handle_error(update, exc)


async def ghrepos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_authorized(update):
        return
    try:
        page = 1
        if context.args:
            if len(context.args) != 1 or not context.args[0].isdigit():
                raise GitHubAPIError("Pemakaian: /ghrepos [halaman]")
            page = int(context.args[0])
        if not 1 <= page <= 20:
            raise GitHubAPIError("Nomor halaman harus antara 1 dan 20.")
        repos = await _get(
            "/user/repos",
            {"sort": "updated", "direction": "desc", "per_page": 10, "page": page, "type": "all"},
        )
        if not repos:
            await update.effective_message.reply_text("Tidak ada repository di halaman ini.")
            return
        lines = [f"<b>Repository GitHub (halaman {page})</b>"]
        for repo in repos:
            visibility = "private" if repo.get("private") else "public"
            lines.append(
                f"• <a href=\"{html.escape(repo.get('html_url', 'https://github.com'), quote=True)}\">"
                f"{html.escape(repo.get('full_name', repo.get('name', '?')))}</a> "
                f"({visibility}, ★ {repo.get('stargazers_count', 0)})"
            )
        lines.append("\nLanjut: /ghrepos " + str(page + 1) if page < 20 else "")
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        await _handle_error(update, exc)


async def ghrepo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_authorized(update):
        return
    try:
        if len(context.args) != 1:
            raise GitHubAPIError("Pemakaian: /ghrepo owner/repo")
        name = _repo_name(context.args[0])
        repo = await _get(f"/repos/{name}")
        license_info = repo.get("license") or {}
        text = (
            f"<b>{html.escape(repo.get('full_name', name))}</b> "
            f"({'private' if repo.get('private') else 'public'})\n"
            f"{html.escape(repo.get('description') or 'Tidak ada deskripsi.')}\n"
            f"⭐ Stars: {repo.get('stargazers_count', 0)} | Forks: {repo.get('forks_count', 0)}\n"
            f"🐛 Open issues: {repo.get('open_issues_count', 0)}\n"
            f"Bahasa: {html.escape(repo.get('language') or '—')}\n"
            f"Default branch: <code>{html.escape(repo.get('default_branch') or '—')}</code>\n"
            f"Lisensi: {html.escape(license_info.get('spdx_id') or '—')}\n"
            f"Terakhir diperbarui: {html.escape((repo.get('updated_at') or '—')[:10])}\n"
            f"<a href=\"{html.escape(repo.get('html_url', 'https://github.com'), quote=True)}\">Buka di GitHub</a>"
        )
        await update.effective_message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        await _handle_error(update, exc)


async def ghissues_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_authorized(update):
        return
    try:
        if len(context.args) != 1:
            raise GitHubAPIError("Pemakaian: /ghissues owner/repo")
        name = _repo_name(context.args[0])
        items = await _get(
            f"/repos/{name}/issues",
            {"state": "open", "sort": "updated", "direction": "desc", "per_page": 20},
        )
        issues = [item for item in items if "pull_request" not in item][:10]
        if not issues:
            await update.effective_message.reply_text(f"Tidak ada issue terbuka di {name}.")
            return
        lines = [f"<b>Issue terbuka — {html.escape(name)}</b>"]
        for issue in issues:
            title = (issue.get("title") or "(tanpa judul)").replace("\n", " ")[:130]
            lines.append(
                f'• <a href="{html.escape(issue.get("html_url", "https://github.com"), quote=True)}">'
                f'#{issue.get("number")}</a> {html.escape(title)}'
            )
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        await _handle_error(update, exc)


async def ghcommits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_authorized(update):
        return
    try:
        if len(context.args) != 1:
            raise GitHubAPIError("Pemakaian: /ghcommits owner/repo")
        name = _repo_name(context.args[0])
        commits = await _get(f"/repos/{name}/commits", {"per_page": 8})
        if not commits:
            await update.effective_message.reply_text(f"Belum ada commit yang bisa ditampilkan untuk {name}.")
            return
        lines = [f"<b>Commit terbaru — {html.escape(name)}</b>"]
        for item in commits[:8]:
            sha = (item.get("sha") or "")[:7]
            message = ((item.get("commit") or {}).get("message") or "(tanpa pesan)").splitlines()[0][:120]
            author = (item.get("author") or {}).get("login") or ((item.get("commit") or {}).get("author") or {}).get("name") or "unknown"
            url = item.get("html_url") or "https://github.com"
            lines.append(
                f'• <a href="{html.escape(url, quote=True)}"><code>{html.escape(sha)}</code></a> '
                f'{html.escape(message)} — {html.escape(author)}'
            )
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        await _handle_error(update, exc)


async def ghfile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_authorized(update):
        return
    try:
        if len(context.args) < 2:
            raise GitHubAPIError("Pemakaian: /ghfile owner/repo path/to/file.py")
        name = _repo_name(context.args[0])
        file_path = " ".join(context.args[1:]).strip().strip("/")
        segments = file_path.split("/")
        if not file_path or any(segment in {"", ".", ".."} for segment in segments):
            raise GitHubAPIError("Path file tidak valid.")
        encoded_path = "/".join(quote(segment, safe="") for segment in segments)
        item = await _get(f"/repos/{name}/contents/{encoded_path}")
        if isinstance(item, list) or item.get("type") != "file":
            raise GitHubAPIError("Path tersebut bukan file biasa.")
        if item.get("size", 0) > 100_000:
            raise GitHubAPIError("File terlalu besar untuk ditampilkan lewat Telegram (maksimal 100 KB).")
        if item.get("encoding") != "base64" or not item.get("content"):
            raise GitHubAPIError("Isi file tidak tersedia melalui endpoint GitHub Contents API.")
        raw = base64.b64decode("".join(item["content"].split()), validate=False)
        content = raw.decode("utf-8", errors="replace")
        truncated = len(content) > 2800
        preview = content[:2800]
        suffix = "\n… (dipotong; buka tautan untuk isi lengkap)" if truncated else ""
        url = item.get("html_url") or "https://github.com"
        text = (
            f'<b>{html.escape(name)}/{html.escape(file_path)}</b>\n'
            f'<a href="{html.escape(url, quote=True)}">Buka file di GitHub</a>\n'
            f"<pre>{html.escape(preview + suffix)}</pre>"
        )
        await update.effective_message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        await _handle_error(update, exc)


def register_github_handlers(application: Application) -> None:
    """Register GitHub command handlers on an existing Telegram Application."""
    handlers = (
        ("github", github_command),
        ("ghrepos", ghrepos_command),
        ("ghrepo", ghrepo_command),
        ("ghissues", ghissues_command),
        ("ghcommits", ghcommits_command),
        ("ghfile", ghfile_command),
    )
    for command, callback in handlers:
        application.add_handler(CommandHandler(command, callback))
