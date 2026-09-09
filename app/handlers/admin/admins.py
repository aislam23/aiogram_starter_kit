"""
Управление администраторами из бота.

Экран «Администраторы» (inline): список, снять права, добавить.
Добавление — через нативный выбор пользователя: reply-кнопка с request_users открывает
в клиенте Telegram список контактов/чатов, бот получает users_shared с ID выбранного.
Пересылать сообщения или вводить username не нужно.

Ограничения:
- админов из ADMIN_USER_IDS (настройки) снять через бота нельзя — только правкой .env;
- себя снять нельзя, чтобы не остаться без админов.
"""
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from loguru import logger

from app.config import settings
from app.database import db
from app.filters import IsAdmin
from app.keyboards import AdminKeyboards
from app.states import AdminStates

router = Router(name="admin_admins")


def _display(user) -> str:
    name = " ".join(filter(None, [user.first_name, user.last_name])) or "без имени"
    handle = f" @{user.username}" if user.username else ""
    return f"<b>{name}</b>{handle} — <code>{user.id}</code>"


async def render_admins() -> tuple[str, "AdminKeyboards"]:
    """Текст и клавиатура экрана «Администраторы»"""
    db_admins = await db.get_admins()
    env_ids = list(settings.admin_user_ids)

    lines = ["👥 <b>Администраторы</b>", ""]
    for user_id in env_ids:
        lines.append(f"• <code>{user_id}</code> — из настроек (ADMIN_USER_IDS)")
    for admin in db_admins:
        if admin.id in env_ids:
            continue
        source = f"по username @{admin.admin_username}" if admin.admin_username else "назначен в боте"
        lines.append(f"• {_display(admin)} — {source}")
    if not env_ids and not db_admins:
        lines.append("Пока никого нет.")
    lines += ["", "Нажмите «➕ Добавить», чтобы выбрать человека из списка контактов."]

    removable = [a.id for a in db_admins if a.id not in env_ids]
    return "\n".join(lines), AdminKeyboards.admins_list(removable)


@router.callback_query(F.data == "admin_manage", IsAdmin())
async def open_admins(callback: CallbackQuery) -> None:
    text, keyboard = await render_admins()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admins:add", IsAdmin())
async def start_pick_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.pick_admin)
    await callback.message.answer(
        "👤 Нажмите кнопку ниже и выберите человека из списка.\n"
        "Он станет администратором сразу, писать боту ему заранее не обязательно.",
        reply_markup=AdminKeyboards.pick_user_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AdminStates.pick_admin), F.users_shared, IsAdmin())
async def receive_picked_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    shared = message.users_shared.users[0] if message.users_shared.users else None
    if not shared:
        await message.answer("Никто не выбран.", reply_markup=ReplyKeyboardRemove())
        return

    await db.add_user(
        user_id=shared.user_id,
        username=shared.username,
        first_name=shared.first_name,
        last_name=shared.last_name,
    )
    await db.set_admin(shared.user_id)
    logger.info(f"👑 Admin {message.from_user.id} granted admin rights to {shared.user_id}")

    who = " ".join(filter(None, [shared.first_name, shared.last_name])) or str(shared.user_id)
    await message.answer(f"✅ <b>{who}</b> (<code>{shared.user_id}</code>) теперь администратор.",
                         reply_markup=ReplyKeyboardRemove())
    text, keyboard = await render_admins()
    await message.answer(text, reply_markup=keyboard)


@router.message(StateFilter(AdminStates.pick_admin), F.text == AdminKeyboards.CANCEL_PICK_TEXT)
async def cancel_pick_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=ReplyKeyboardRemove())


@router.message(StateFilter(AdminStates.pick_admin))
async def abandon_pick_admin(message: Message, state: FSMContext) -> None:
    """Пользователь в режиме выбора написал что-то другое (текст, команду) — выходим и убираем клавиатуру.

    Без этого хендлера состояние осталось бы висеть, а reply-клавиатура — торчать в чате.
    Объявлен ПОСЛЕ хендлеров users_shared и «Отмена», иначе перехватил бы их.
    """
    await state.clear()
    hint = " Повторите команду." if (message.text or "").startswith("/") else ""
    await message.answer(f"Выбор администратора отменён.{hint}", reply_markup=ReplyKeyboardRemove())


@router.callback_query(F.data.startswith("admins:remove:"), IsAdmin())
async def remove_admin(callback: CallbackQuery) -> None:
    user_id = int(callback.data.rsplit(":", 1)[1])
    if user_id == callback.from_user.id:
        await callback.answer("Нельзя снять права с самого себя", show_alert=True)
        return
    if settings.is_admin(user_id):
        await callback.answer("Этот админ задан в настройках (ADMIN_USER_IDS), уберите его из .env", show_alert=True)
        return

    await db.remove_admin(user_id)
    logger.info(f"👑 Admin {callback.from_user.id} revoked admin rights from {user_id}")
    text, keyboard = await render_admins()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer("Права сняты")


@router.callback_query(F.data == "admins:back", IsAdmin())
async def back_to_panel(callback: CallbackQuery) -> None:
    from .admin import admin_panel_text

    await callback.message.edit_text(await admin_panel_text(), reply_markup=AdminKeyboards.main_admin_menu())
    await callback.answer()
