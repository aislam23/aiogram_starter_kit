"""
Состояния для админской части
"""
from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Состояния для админских функций"""

    # Состояния для рассылки
    broadcast_message = State()  # Ожидание сообщения для рассылки
    broadcast_button = State()   # Ожидание кнопки для рассылки
    broadcast_confirm = State()  # Подтверждение рассылки

    # Управление админами
    pick_admin = State()         # Ожидание выбора пользователя через request_users
