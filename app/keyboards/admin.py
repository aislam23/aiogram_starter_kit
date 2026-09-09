"""
Клавиатуры для админской части
"""
from typing import Iterable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestUsers,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


class AdminKeyboards:
    """Клавиатуры для админской панели"""

    @staticmethod
    def main_admin_menu() -> InlineKeyboardMarkup:
        """Главное меню админа"""
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="📊 Рассылка",
            callback_data="admin_broadcast"
        ))

        builder.add(InlineKeyboardButton(
            text="👥 Администраторы",
            callback_data="admin_manage"
        ))

        builder.add(InlineKeyboardButton(
            text="⚙️ Настройки API",
            callback_data="admin_api_settings"
        ))

        builder.adjust(1)
        return builder.as_markup()

    PICK_ADMIN_REQUEST_ID = 1
    CANCEL_PICK_TEXT = "❌ Отмена"

    @staticmethod
    def admins_list(removable_ids: Iterable[int]) -> InlineKeyboardMarkup:
        """Экран «Администраторы»: снять права (только у тех, кого можно), добавить, назад"""
        builder = InlineKeyboardBuilder()
        for user_id in removable_ids:
            builder.button(text=f"➖ Снять {user_id}", callback_data=f"admins:remove:{user_id}")
        builder.button(text="➕ Добавить администратора", callback_data="admins:add")
        builder.button(text="⬅️ Назад", callback_data="admins:back")
        builder.adjust(1)
        return builder.as_markup()

    @classmethod
    def pick_user_keyboard(cls) -> ReplyKeyboardMarkup:
        """Reply-клавиатура с нативным выбором пользователя (request_users).

        Inline-кнопки так не умеют: выбор контакта открывает только KeyboardButton.
        Клиент Telegram покажет список чатов/контактов и пришлёт боту users_shared с ID выбранного.
        """
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(
                    text="👤 Выбрать пользователя",
                    request_users=KeyboardButtonRequestUsers(
                        request_id=cls.PICK_ADMIN_REQUEST_ID,
                        user_is_bot=False,
                        max_quantity=1,
                        request_name=True,
                        request_username=True,
                    ),
                )],
                [KeyboardButton(text=cls.CANCEL_PICK_TEXT)],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    @staticmethod
    def broadcast_confirm(message_count: int) -> InlineKeyboardMarkup:
        """Подтверждение рассылки"""
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text=f"✅ Отправить ({message_count} польз.)",
            callback_data="broadcast_confirm_yes"
        ))

        builder.add(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="broadcast_confirm_no"
        ))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def broadcast_add_button() -> InlineKeyboardMarkup:
        """Меню добавления кнопки к рассылке"""
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="➕ Добавить кнопку",
            callback_data="broadcast_add_button"
        ))

        builder.add(InlineKeyboardButton(
            text="📤 Отправить без кнопки",
            callback_data="broadcast_no_button"
        ))

        builder.add(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="broadcast_cancel"
        ))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def broadcast_button_confirm() -> InlineKeyboardMarkup:
        """Подтверждение кнопки для рассылки"""
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data="broadcast_button_confirm"
        ))

        builder.add(InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="broadcast_cancel"
        ))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def create_custom_button(text: str, url: str) -> InlineKeyboardMarkup:
        """Создание кастомной кнопки для рассылки"""
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text=text,
            url=url
        ))

        return builder.as_markup()

    @staticmethod
    def api_settings_menu(is_local_mode: bool) -> InlineKeyboardMarkup:
        """Меню настроек API"""
        builder = InlineKeyboardBuilder()

        switch_text = "🌍 Перейти на Public API" if is_local_mode else "🟢 Перейти на Local API"
        builder.add(InlineKeyboardButton(
            text=switch_text,
            callback_data="api_switch_mode"
        ))

        builder.add(InlineKeyboardButton(
            text="📊 Проверить статус",
            callback_data="api_check_status"
        ))

        builder.add(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="api_back"
        ))

        builder.adjust(1)
        return builder.as_markup()

    @staticmethod
    def api_settings_back() -> InlineKeyboardMarkup:
        """Кнопка возврата из инструкций"""
        builder = InlineKeyboardBuilder()

        builder.add(InlineKeyboardButton(
            text="◀️ Назад к настройкам",
            callback_data="admin_api_settings"
        ))

        builder.adjust(1)
        return builder.as_markup()
