# Деплой на сервер без секретов в чате — дизайн

Дата: 2026-09-10. Статус: согласован с автором шаблона.

## Проблема

Ученики не понимают, что такое `.env`, и не могут безопасно передать агенту данные сервера
(IP, пароль, ключ). Сейчас деплой требует 10 ручных шагов на сервере (`docs/SERVER_SETUP.md`)
и ручного ввода секретов на GitHub. Токен бота уже вводится безопасно (`just set-token`) —
нужен такой же путь для сервера.

## Цели

1. Человек **никогда** не вставляет IP/пароль/ключ в чат с агентом. Всё — через локальную
   страницу в браузере, как в `set_token.py`.
2. Пароль от сервера **не хранится**: используется один раз, чтобы установить наш SSH-ключ.
   Дальше вход только по ключу из `.deploy/`.
3. Два полноценных пути деплоя на одном коде:
   - **прямой** — `just deploy` с ноутбука по SSH;
   - **GitHub Actions** — `just deploy-github` публикует секреты через `gh` CLI, дальше каждый
     `git push` в `main` деплоит сам.
4. Если сервера нет — `just rent-server` показывает провайдеров с реферальными ссылками автора
   и открывает выбранную в браузере. На странице честно подписано «партнёрская ссылка».
5. Кроссплатформенно (Windows без `sshpass`/`rsync`): SSH через `paramiko` в dev-зависимостях.

## Компоненты

| Файл | Назначение |
|---|---|
| `scripts/providers.py` | Список провайдеров (`vdska` — основной, первый). `--json` для агента, `open <slug>` открывает ссылку. |
| `scripts/server_config.py` | Общий слой: `ServerConfig` (host, port, user, key_file, project_path), чтение/запись `.deploy/server.json`, `mask_host`, генерация ключа ed25519, обёртка над paramiko (`SshSession`: `run`, `upload_bytes`, `upload_file`). paramiko импортируется лениво. |
| `scripts/set_server.py` | Страница в браузере: хост, порт, пользователь, «пароль» или «приватный ключ». Проверяет вход, генерирует `.deploy/deploy_key`, дописывает его в `~/.ssh/authorized_keys` на сервере, пишет `.deploy/server.json`. Печатает только `✅ Сервер подключён: root@123.45.•.• (вход по ключу)`. CLI-режим без браузера принимает `--host --user --port --key-file` (без пароля). |
| `scripts/remote_deploy.py` | `deploy` / `logs [N]` / `status`. Источник настроек: `.deploy/server.json` либо флаги/переменные окружения (для CI). Ставит Docker, если нет; загружает tar проекта (`git ls-files`, без `.env*`, `.deploy`, `.git`) и `.env.prod` (0600); запускает на сервере `python3 scripts/deploy.py --ci`; печатает вывод. |
| `scripts/github_secrets.py` | Через `gh secret set`: `SERVER_HOST`, `SERVER_PORT`, `SERVER_USER`, `SSH_PRIVATE_KEY`, `PROJECT_PATH`, `ENV_PROD` (содержимое `.env.prod`). Проверяет `gh auth status` и наличие `origin`. Значения не печатает. |
| `.github/workflows/deploy.yml` | Job `deploy` на раннере: checkout → pip install paramiko → ключ и `.env.prod` из секретов во временные файлы → `python scripts/remote_deploy.py deploy`. Пропуск, если `SERVER_HOST` пуст. |
| `scripts/deploy.py` | Целевое улучшение: автоопределение `docker compose` v2 / `docker-compose` v1 (сейчас жёстко v1 — ломается на свежем Ubuntu). |
| `scripts/doctor.py` | Проверка «Сервер»: `.deploy/server.json` есть/нет, ключ на месте (необязательная, с маской). |
| `justfile`, `Makefile` | `rent-server [slug]`, `set-server`, `deploy`, `server-logs [N]`, `server-status`, `deploy-github`. |
| `.gitignore`, `.claude/settings.json`, `scripts/check_secrets.py` | `.deploy/` игнорируется, запрещён к чтению агенту, пропускается сканером. |
| `requirements-dev.txt` | `paramiko`. |
| `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/SERVER_SETUP.md` | Новый сценарий «сервер через агента»; ручной путь остаётся приложением. |

## Поток для ученика (через агента)

```
Агент: «Есть ли у вас сервер?»
  нет → just rent-server           # список; агент спрашивает, какой
        just rent-server vdska     # открылась реферальная ссылка, человек регистрируется
Агент: «Скопируйте IP и пароль root из письма провайдера; сейчас откроется страница»
        just set-server            # человек вставляет на странице; агент видит только маску
        just deploy                # Docker, загрузка, запуск, health
        just server-logs 30        # проверка
  опционально:
        just deploy-github         # секреты в GitHub через gh; дальше деплой по git push
```

## Безопасность

- `.deploy/` — права 0700, файлы 0600, в `.gitignore`, deny в `.claude/settings.json`.
- В stdout: хост под маской (`123.45.•.•` / `srv…example.com`), пользователь, порт. Ключи и пароли — никогда.
- Пароль живёт только в памяти процесса `set_server.py` до установки ключа.
- `remote_deploy` не загружает `.env` (dev), `.deploy/`, `.git/`, `.venv/`, `logs/`.

## Тестирование

Как у `set_token`: чистые функции и сервер формы тестируются без сети (фейковые
`connect`/`run`). Проверяются: формат хоста/порта, маска, запись `server.json`,
генерация ключа, состав tar-архива, список команд для `gh`, автоопределение compose,
проверка «Сервер» в doctor. `just check` зелёный — критерий готовности.
