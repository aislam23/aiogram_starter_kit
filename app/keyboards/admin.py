"""
Клавиатуры для админской части
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
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
            text="⚙️ Настройки API",
            callback_data="admin_api_settings"
        ))

        builder.adjust(1)
        return builder.as_markup()

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
