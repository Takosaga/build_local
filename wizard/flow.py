"""
Flow logic: determines the current mode (setup vs ongoing) and
enforces the maximum question count during info-gathering step.
Question count is stored in wizard business_data to persist across restarts.
"""
from wizard.state import get_state, update_business_data

QUESTION_KEY = "_questions_asked"
MAX_QUESTIONS = 5


def get_mode() -> str:
    """Returns 'setup' or 'ongoing'."""
    return "ongoing" if get_state().is_complete else "setup"


def get_questions_asked() -> int:
    state = get_state()
    return state.business_data.get(QUESTION_KEY, 0)


def increment_questions_asked():
    count = get_questions_asked()
    update_business_data({QUESTION_KEY: count + 1})


def should_advance_from_info_step() -> bool:
    return get_questions_asked() >= MAX_QUESTIONS
