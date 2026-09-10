#!/usr/bin/env python3
"""
Где арендовать сервер для бота: список провайдеров с партнёрскими ссылками автора шаблона.

Usage:
    python scripts/providers.py              # список для человека
    python scripts/providers.py --json       # список для агента
    python scripts/providers.py vdska        # открыть ссылку провайдера в браузере

Ссылки партнёрские: автор шаблона получает вознаграждение, цена для вас не меняется.
Чтобы поменять список — правьте только PROVIDERS ниже.
"""
from __future__ import annotations

import json
import sys
import webbrowser
from dataclasses import asdict, dataclass
from typing import Callable, List, Optional


@dataclass(frozen=True)
class Provider:
    slug: str
    name: str
    url: str
    note: str


# Первый в списке — основной: агент предлагает его по умолчанию.
PROVIDERS: List[Provider] = [
    Provider("vdska", "VDSka", "https://vdska.ru/?p=9888", "Основной вариант: дёшево, оплата картой РФ"),
    Provider("timeweb", "Timeweb Cloud", "https://timeweb.cloud/r/cj28624", "Популярный в РФ, простой интерфейс"),
    Provider("reg", "Reg.ru Cloud", "https://reg.cloud/cloud/servers/?rlink=reflink-32393957", "Крупный российский хостинг"),
    Provider("beget", "Beget", "https://beget.com/p2246004", "Российский, есть поддержка 24/7"),
    Provider("aeza", "Aeza", "https://aeza.net/?ref=427553", "Серверы в РФ и Европе"),
    Provider("linkhost", "Link-Host", "https://link-host.net/billing/pl.php?1786", "Бюджетные VDS"),
    Provider("racknerd", "RackNerd", "https://my.racknerd.com/aff.php?aff=17494", "Зарубежный, оплата иностранной картой"),
]

PRIMARY = PROVIDERS[0]


def find(slug: str) -> Optional[Provider]:
    """Найти провайдера по slug без учёта регистра."""
    wanted = (slug or "").strip().lower()
    return next((p for p in PROVIDERS if p.slug == wanted), None)


def as_json() -> str:
    return json.dumps({"primary": PRIMARY.slug, "providers": [asdict(p) for p in PROVIDERS]}, ensure_ascii=False)


def render_list() -> str:
    lines = ["🖥  Где арендовать сервер (Ubuntu 22.04+, от 1 ГБ RAM):", ""]
    for p in PROVIDERS:
        marker = "★" if p is PRIMARY else " "
        lines.append(f"  {marker} {p.slug:<9} {p.name:<15} {p.note}")
    lines += ["", "Открыть в браузере: just rent-server <slug>   (например: just rent-server vdska)",
              "Ссылки партнёрские — автор шаблона получает вознаграждение, цена для вас не меняется."]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None, opener: Callable[[str], object] = webbrowser.open) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--json" in args:
        print(as_json())
        return 0
    if not args:
        print(render_list())
        return 0
    provider = find(args[0])
    if provider is None:
        print(f"❌ Провайдер «{args[0]}» не найден. Доступные:\n")
        print(render_list())
        return 1
    opener(provider.url)
    print(f"🌐 Открываю {provider.name} ({provider.slug}) в браузере…")
    print(f"   Если страница не открылась: {provider.url}")
    print("   Зарегистрируйтесь, создайте сервер с Ubuntu, и держите под рукой IP-адрес и пароль root.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
