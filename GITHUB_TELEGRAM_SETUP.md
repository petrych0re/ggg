# Integrasi GitHub ke bot Telegram

Modul `github_integration.py` menambahkan perintah baca-saja untuk GitHub ke aplikasi Telegram yang memakai **python-telegram-bot v20+**. Modul ini membantu admin memeriksa repository, issue terbuka, commit terbaru, dan isi file tanpa harus keluar dari Telegram.

> Repo ini belum menyertakan file utama bot Telegram (`bot.py`). Karena itu, modul disediakan terpisah dan harus didaftarkan ke aplikasi bot yang sudah ada.

## 1. Pasang dependensi

Di folder proyek bot, jalankan:

```bash
python -m pip install -r requirements-bot.txt
```

Simpan/copy `github_integration.py` di folder yang sama dengan file utama bot.

## 2. Atur file .env

Tambahkan variabel berikut ke file `.env` lokal. Jangan commit file `.env` ke GitHub.

```dotenv
GITHUB_TOKEN=github_pat_ganti_dengan_token_milikmu
GITHUB_ALLOWED_TELEGRAM_IDS=123456789
```

Ganti `123456789` dengan Telegram numeric user ID milik admin yang diizinkan. Untuk beberapa admin, pisahkan dengan koma, misalnya `123456789,987654321`. Jika variabel ini kosong, modul akan memakai `ADMIN_ID` yang sudah digunakan proyek. Nilai `ADMIN_ID=0` tidak memberikan akses kepada siapa pun.

Buat GitHub fine-grained personal access token dengan akses baca minimum. Untuk repository privat, pilih repository yang dibutuhkan dan berikan izin **Metadata: read-only**, serta izin **Contents: read-only** dan **Issues: read-only** bila ingin membaca file dan issue. Hindari izin write/admin. Jangan kirim token ke chat Telegram, log, atau screenshot.

## 3. Sambungkan ke aplikasi bot

Tambahkan import dan pemanggilan fungsi berikut pada file utama bot yang memakai `python-telegram-bot`. Jalankan registrasi sebelum `application.run_polling()`.

```python
from github_integration import register_github_handlers

# Setelah objek Application dibuat:
register_github_handlers(application)
```

Jika bot saat ini memakai framework lain seperti `aiogram` atau `pyTelegramBotAPI`, handler perlu diadaptasi ke framework tersebut; modul ini tidak kompatibel langsung dengan semua framework.

## 4. Perintah Telegram

| Perintah | Fungsi |
|---|---|
| `/github` | Memastikan token terhubung dan menampilkan akun GitHub yang terautentikasi |
| `/ghrepos [halaman]` | Daftar 10 repository per halaman, diurutkan berdasarkan pembaruan |
| `/ghrepo owner/repo` | Ringkasan repository, branch utama, stars, forks, dan issue |
| `/ghissues owner/repo` | Menampilkan issue terbuka (pull request dikecualikan) |
| `/ghcommits owner/repo` | Menampilkan hingga 8 commit terbaru |
| `/ghfile owner/repo path/file.py` | Menampilkan preview file teks, maksimal 100 KB dan dipotong untuk Telegram |

Contoh: `/ghrepo petrych0re/ggg`

Semua perintah dibatasi ke ID Telegram admin dan hanya memakai HTTP GET. Modul tidak membuat commit, mengubah branch, menghapus file, atau mengirim perubahan ke GitHub.

## Catatan keamanan

- Simpan token hanya di environment atau file `.env` lokal yang tidak di-commit.
- Batasi daftar repository pada token hanya ke repository yang benar-benar diperlukan.
- Perintah dibatasi dengan allowlist ID Telegram. Pastikan ID admin benar.
- Jangan mengekspos bot token atau GitHub token lewat pesan/log.
- Respons GitHub yang tidak ditemukan dapat berarti repository privat tidak termasuk dalam cakupan token.
