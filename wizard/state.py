from dataclasses import dataclass, field
import db.session as session


@dataclass
class WizardState:
    current_step: int
    completed_steps: list[int]
    business_data: dict
    is_complete: bool


def get_state() -> WizardState:
    raw = session.load_wizard_state()
    return WizardState(**raw)


def advance_step(business_data: dict | None = None):
    state = get_state()
    if business_data:
        merged = {**state.business_data, **business_data}
    else:
        merged = state.business_data
    completed = list(set(state.completed_steps + [state.current_step]))
    session.save_wizard_state(
        current_step=state.current_step + 1,
        completed_steps=completed,
        business_data=merged,
    )


def update_business_data(data: dict):
    state = get_state()
    merged = {**state.business_data, **data}
    session.save_wizard_state(
        current_step=state.current_step,
        completed_steps=state.completed_steps,
        business_data=merged,
    )


def mark_complete():
    state = get_state()
    session.save_wizard_state(
        current_step=state.current_step,
        completed_steps=state.completed_steps,
        business_data=state.business_data,
        is_complete=True,
    )


def reset():
    session.save_wizard_state(
        current_step=0,
        completed_steps=[],
        business_data={},
        is_complete=False,
    )
