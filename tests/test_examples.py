"""
Тесты примеров хендлеров (app/handlers/examples). Включаются через EXAMPLE_HANDLERS=true.
"""
from tests.harness import buttons_of, callbacks_of

# ── /survey: FSM-анкета из нескольких шагов ──────────────────────

async def test_survey_asks_name_first(harness, user):
    replies = await harness.send_message("/survey", user)
    assert "зовут" in replies[0].text.lower()
    assert await harness.state_of(user) == "SurveyStates:name"


async def test_survey_then_asks_age(harness, user):
    await harness.send_message("/survey", user)
    replies = await harness.send_message("Артём", user)
    assert "лет" in replies[0].text.lower()
    assert await harness.state_of(user) == "SurveyStates:age"


async def test_survey_rejects_non_numeric_age_and_stays(harness, user):
    await harness.send_message("/survey", user)
    await harness.send_message("Артём", user)
    replies = await harness.send_message("много", user)
    assert "числ" in replies[0].text.lower()
    assert await harness.state_of(user) == "SurveyStates:age"


async def test_survey_shows_summary_with_confirm_buttons(harness, user):
    await harness.send_message("/survey", user)
    await harness.send_message("Артём", user)
    replies = await harness.send_message("30", user)
    assert "Артём" in replies[0].text
    assert "30" in replies[0].text
    assert "survey:confirm" in callbacks_of(replies[0])
    assert "survey:cancel" in callbacks_of(replies[0])


async def test_survey_confirm_finishes_and_clears_state(harness, user):
    await harness.send_message("/survey", user)
    await harness.send_message("Артём", user)
    await harness.send_message("30", user)
    replies = await harness.send_callback("survey:confirm", user)
    assert "сохран" in replies[0].text.lower()
    assert await harness.state_of(user) is None


async def test_survey_cancel_command_clears_state(harness, user):
    await harness.send_message("/survey", user)
    replies = await harness.send_message("/cancel", user)
    assert "отмен" in replies[0].text.lower()
    assert await harness.state_of(user) is None


# ── /items: пагинация через callback_data ────────────────────────

async def test_items_shows_first_page_with_next_button(harness, user):
    replies = await harness.send_message("/items", user)
    assert "Страница 1" in replies[0].text
    assert "▶️" in buttons_of(replies[0])
    assert "◀️" not in buttons_of(replies[0])


async def test_items_next_page_edits_message(harness, user):
    from app.handlers.examples.pagination import ItemsPage

    await harness.send_message("/items", user)
    replies = await harness.send_callback(ItemsPage(page=2).pack(), user)
    assert replies[0].__class__.__name__ == "EditMessageText"
    assert "Страница 2" in replies[0].text
    assert "◀️" in buttons_of(replies[0])
