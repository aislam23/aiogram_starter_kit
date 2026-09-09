"""
Пример: список с постраничной навигацией.

Паттерн:
- CallbackData-фабрика вместо ручного разбора строк: `ItemsPage(page=2).pack()` → "items:2".
- Команда отправляет первую страницу, кнопки редактируют то же сообщение.
- Клавиатура строится одной функцией, чтобы первая и последующие страницы выглядели одинаково.

Замените ITEMS на выборку из БД: `items = await db.get_items(offset=..., limit=PAGE_SIZE)`.
"""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router(name="example_pagination")

PAGE_SIZE = 5
ITEMS = [f"Элемент №{i}" for i in range(1, 24)]


class ItemsPage(CallbackData, prefix="items", sep=":"):
    page: int


def render_page(page: int) -> tuple[str, InlineKeyboardMarkup]:
    total_pages = max(1, (len(ITEMS) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(page, 1), total_pages)
    start = (page - 1) * PAGE_SIZE
    chunk = ITEMS[start:start + PAGE_SIZE]

    text = f"📋 <b>Список</b> — Страница {page} из {total_pages}\n\n" + "\n".join(f"• {item}" for item in chunk)

    builder = InlineKeyboardBuilder()
    if page > 1:
        builder.button(text="◀️", callback_data=ItemsPage(page=page - 1))
    if page < total_pages:
        builder.button(text="▶️", callback_data=ItemsPage(page=page + 1))
    builder.adjust(2)
    return text, builder.as_markup()


@router.message(Command("items"))
async def items_command(message: Message) -> None:
    text, keyboard = render_page(1)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(ItemsPage.filter(F.page))
async def items_page(callback: CallbackQuery, callback_data: ItemsPage) -> None:
    text, keyboard = render_page(callback_data.page)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
