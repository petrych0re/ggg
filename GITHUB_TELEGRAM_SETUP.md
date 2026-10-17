# Telegram AI + GitHub Bot

This repository now includes a runnable Telegram bot entry point (`bot.py`) and a read-only GitHub command module (`github_integration.py`). The bot can answer ordinary text messages using the OpenAI API, and admins can inspect GitHub repositories from Telegram.

## Important: use the feature branch

These changes are currently in the pull request branch `feature/telegram-github-integration`, not in `main` until the PR is merged. To try the code before it is merged:

```bash
git clone --branch feature/telegram-github-integration https://github.com/petrych0re/ggg.git
cd ggg
```

After the PR is merged, clone the default branch instead.

## 1. Install Python dependencies

Use Python 3.10 or later. In the project folder:

```bash
python -m venv .venv
```

On Windows PowerShell, activate the environment:

```powershell
.venv\Scripts\Activate.ps1
```

Then install packages:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-bot.txt
```

## 2. Configure secrets and access

Copy `.env.example` to a local file named `.env`. Replace each placeholder:

- `TELEGRAM_BOT_TOKEN`: token from BotFather for your Telegram bot.
- `OPENAI_API_KEY`: your OpenAI API key. **API usage is billed separately from a ChatGPT subscription.** Set an appropriate budget/usage limit on the API account.
- `GITHUB_TOKEN`: a GitHub fine-grained personal access token limited to the repository or repositories you need. Grant only read access: Metadata, Contents (for `/ghfile`), and Issues (for `/ghissues`). If the token type/account doesn't permit the account-profile endpoint used by `/github`, that command may need a token/endpoint adjustment.
- `BOT_ALLOWED_TELEGRAM_IDS`: comma-separated numeric Telegram IDs permitted to use the AI bot.
- `ADMIN_ID`: comma-separated numeric Telegram IDs permitted to use admin commands such as `/ai_on` and `/ai_off`.
- `GITHUB_ALLOWED_TELEGRAM_IDS`: comma-separated numeric Telegram IDs allowed to run GitHub commands.

To discover your own numeric Telegram ID, start the bot and send `/myid`. This helper responds only with the ID of the user who sent the command. Stop the bot, place your ID into all three allowlist variables as needed, save `.env`, and restart the bot. Access defaults to restricted if no allowlist is configured.

Never commit `.env` or paste your tokens into a Telegram chat, source code, issue, or screenshot.

## 3. Start the bot

```bash
python bot.py
```

Keep the process running while you use the bot. To keep it available around the clock, deploy it on a trusted machine or server and store secrets in that environment. The Windows control application elsewhere in this repository is optional and is not required to run `bot.py`.

## 4. Commands in Telegram

| Command | What it does |
|---|---|
| `/myid` | Shows your own numeric Telegram ID for local allowlist setup |
| `/start` | Starts the bot and displays a summary |
| `/help` | Lists commands |
| `/status` | Shows whether AI, MySQL, and GitHub token settings are configured |
| `/reset` | Clears your conversation history in MySQL and the in-memory session |
| `/ai_on` | Enables AI chat; admin only |
| `/ai_off` | Disables AI chat; admin only |
| `/github` | Tests GitHub authentication and shows the connected account |
| `/ghrepos [page]` | Lists repositories visible to the GitHub token |
| `/ghrepo owner/repo` | Shows repository metadata |
| `/ghissues owner/repo` | Lists open issues (pull requests are excluded) |
| `/ghcommits owner/repo` | Lists recent commits |
| `/ghfile owner/repo path/to/file.py` | Shows a short preview of a text file |

Example:

```text
/ghrepo petrych0re/ggg
/ghcommits petrych0re/ggg
/ghfile petrych0re/ggg bot.py
```

GitHub commands use read-only GET requests. They do not create commits, edit files, modify branches, or delete repository content.

## 5. Optional: save chat history in MySQL via Navicat

The bot can run without MySQL; in that mode history is held only in process memory and is lost when the process restarts.

**For a new database:**
1. Start MySQL Server and connect through Navicat Premium.
2. Open and execute `telegram-ai-navicat/setup_telegram_ai.sql`.
3. Confirm that database `telegram_ai` and tables `users`, `chat_history`, and `bot_settings` were created.
4. Fill in `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE` in local `.env`.
5. Set `MYSQL_ENABLED=1` and restart the bot.

**For a database that already exists from the older SQL script:**
1. Open and execute `telegram-ai-navicat/upgrade_telegram_ai.sql` in Navicat.
2. This adds the history lookup index only if it is missing and inserts default settings only when absent. It does not delete existing chat records.
3. Set `MYSQL_ENABLED=1` in the local `.env` and restart the bot.

Use a dedicated MySQL user with only the database permissions it needs instead of using `root` for regular operation. Keep the database on localhost or a trusted private network. Do not store API keys or bot tokens in the database.

## Troubleshooting

- **Bot does not start:** make sure `TELEGRAM_BOT_TOKEN` is set and the dependencies installed in the active Python environment.
- **AI says the key is missing/invalid:** check `OPENAI_API_KEY`, API account access, available usage budget, and `OPENAI_MODEL`.
- **GitHub responds with 404:** a private repository can appear not found when the token has no access to it.
- **GitHub responds with 401/403:** check the token, expiry, selected repositories, permissions, and API rate limit.
- **MySQL errors:** confirm the server is running, the credentials are correct, and the SQL setup was imported before enabling persistence.
- **Commands are denied:** verify your numeric ID in `BOT_ALLOWED_TELEGRAM_IDS`, `ADMIN_ID`, and `GITHUB_ALLOWED_TELEGRAM_IDS`. Restart after editing `.env`.

The bot has not been live-tested against your Telegram account or API keys; those credentials must be configured locally before end-to-end use.
