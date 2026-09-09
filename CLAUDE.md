# CLAUDE.md

Guidance for Claude Code when working in this repository.

**Read `AGENTS.md` first.** It is the full playbook: setup flow, verification commands, recipes for
every common task, and the rules about secrets. This file only lists what is Claude-specific.

## Non-negotiable rules

- **Never ask the user to paste a bot token, password or API key into the chat.** Use `just set-token`.
  The user copies the token from @BotFather; the script takes it from the clipboard or a local browser
  page and prints only `@bot_name connected` with a masked token.
- `.env`, `.env.prod` and other `.env.*` files are denied for reading in `.claude/settings.json`. Do not
  work around it with `cat`, `sed`, `grep` or Python. Use `just doctor --json` to learn what is configured.
- Run `just check` after every code change (ruff + pytest + secrets scan, no Docker). Do not report a task
  as done while it is red.
- Codebase language: Russian for comments, docstrings and user-facing messages; English identifiers.

## Quick reference

```bash
just venv                      # one-time: .venv with dev deps
just init <name> <@username|id> # non-interactive setup; ask for the username, the bot resolves the ID
just set-token                 # safe token entry (human-only step)
just doctor [--json]           # environment check
just check                     # lint + tests + secrets
just dev-d / just stop         # run / stop with Docker
just logs-json 50              # read logs/bot.jsonl (masked)
```

## Architecture in one paragraph

`app/main.py` builds `Bot` + `Dispatcher`, registers outer middlewares (`app/middlewares`), routers
(`app/handlers/__init__.py`, order matters), runs migrations on startup and starts polling. Settings come
from `app/config.py` (`settings`). Database access goes through the `db` singleton in `app/database`.
FSM states live in `app/states` with Redis storage. Tests use `tests/harness.py` to feed updates through the
real dispatcher with a fake Telegram session; `fake_db` replaces `db` methods in memory.

## When adding features

Follow the numbered recipe in `AGENTS.md` §4 for the task type (command, FSM flow, callback buttons,
new table, migration, service, middleware, admin button, external API). Copy the referenced example file
rather than inventing a new structure. Write the test first with the harness, then the handler.
