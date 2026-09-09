"""
Пример: FSM-анкета из нескольких шагов.

Паттерн:
1. Команда переводит пользователя в первое состояние.
2. Каждый шаг: хендлер с StateFilter читает ответ, валидирует, сохраняет в state.update_data(),
   переводит в следующее состояние.
3. Последний шаг показывает сводку с inline-кнопками подтверждения.
4. /cancel в любом состоянии анкеты сбрасывает её.

Чтобы сделать свою анкету: скопируйте файл, переименуйте SurveyStates и команды,
замените шаги, зарегистрируйте роутер в app/handlers/__init__.py.
"""
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

router = Router(name="example_survey")


class SurveyStates(StatesGroup):
    name = State()
    age = State()
    confirm = State()


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Всё верно", callback_data="survey:confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="survey:cancel"),
    ]])


@router.message(Command("survey"))
async def survey_start(message: Message, state: FSMContext) -> None:
    await state.set_state(SurveyStates.name)
    await message.answer("📝 Небольшая анкета.\n\nКак вас зовут?\n\nДля отмены введите /cancel")


@router.message(Command("cancel"), StateFilter(SurveyStates))
async def survey_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Анкета отменена")


@router.message(StateFilter(SurveyStates.name), F.text)
async def survey_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(SurveyStates.age)
    await message.answer("Сколько вам лет?")


@router.message(StateFilter(SurveyStates.age), F.text)
async def survey_age(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("Введите возраст числом, например: 30")
        return
    await state.update_data(age=int(message.text.strip()))
    await state.set_state(SurveyStates.confirm)

    data = await state.get_data()
    await message.answer(
        f"Проверьте данные:\n\n👤 Имя: <b>{data['name']}</b>\n🎂 Возраст: <b>{data['age']}</b>",
        reply_markup=confirm_keyboard(),
    )


@router.callback_query(F.data == "survey:confirm", StateFilter(SurveyStates.confirm))
async def survey_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    logger.info(f"📝 Survey completed by {callback.from_user.id}: {data}")
    # Здесь обычно сохранение в БД: await db.save_survey(callback.from_user.id, data)
    await callback.message.edit_text("✅ Спасибо, анкета сохранена!")
    await callback.answer()


@router.callback_query(F.data == "survey:cancel", StateFilter(SurveyStates))
async def survey_cancel_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Анкета отменена")
    await callback.answer()
