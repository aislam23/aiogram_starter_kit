# CLAUDE.md

Guidance for Claude Code when working in this repository.

**Read `AGENTS.md` first.** It is the full playbook: setup flow, verification commands, recipes for
every common task, and the rules about secrets. This file only lists what is Claude-specific.

## Non-negotiable rules

- **Never ask the user to paste a bot token, server IP, password, SSH key or API key into the chat.**
  Token: `just set-token` (clipboard or a local browser page; prints only `@bot_name connected`).
  Server: `just set-server` (local browser page for IP + password; the password is used once to install our
  SSH key and is never stored; prints only `root@123.45.•.•`). No server yet: `just rent-server`.
- `.env`, `.env.prod`, other `.env.*` files and the `.deploy/` directory are denied for reading in
  `.claude/settings.json`. Do not work around it with `cat`, `sed`, `grep` or Python. Use `just doctor --json`
  to learn what is configured.
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
just rent-server [slug]        # where to rent a server; opens the author's partner link in the browser
just set-server                # safe server entry (human-only step; needs `just venv` once)
just deploy                    # deploy over SSH: Docker, upload, compose up, health
just server-logs 30            # bot logs from the server
just deploy-github             # publish deploy secrets to GitHub Actions via gh CLI
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
