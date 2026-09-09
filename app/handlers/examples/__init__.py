"""
Примеры хендлеров — образцы паттернов для копирования.

Включаются переменной EXAMPLE_HANDLERS=true (в .env.example включены, в продакшене выключены).
Когда у бота появятся свои сценарии, удалите эту папку и строку в app/handlers/__init__.py.

- survey.py      — FSM-анкета из нескольких шагов с валидацией и подтверждением
- pagination.py  — список с постраничной навигацией через CallbackData
"""
from aiogram import Router

from .pagination import router as pagination_router
from .survey import router as survey_router

router = Router(name="examples")
router.include_router(survey_router)
router.include_router(pagination_router)

__all__ = ["router"]
