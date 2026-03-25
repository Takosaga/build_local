from llm.prompts import get_greet_prompt


def test_greet_prompt_step1_contains_data_decision_question():
    prompt = get_greet_prompt(1, "Bloom Flowers", "flower shop", "Manchester")
    assert "import" in prompt.lower() or "demo" in prompt.lower()
    assert "Bloom Flowers" in prompt


def test_greet_prompt_step2_contains_inventory_question():
    prompt = get_greet_prompt(2, "Bloom Flowers", "flower shop", "Manchester")
    assert "inventor" in prompt.lower() or "stock" in prompt.lower()
    assert "Bloom Flowers" in prompt


def test_greet_prompt_step3_contains_summary_instruction():
    prompt = get_greet_prompt(3, "Bloom Flowers", "flower shop", "Manchester")
    assert "summar" in prompt.lower() or "configured" in prompt.lower()
    assert "Bloom Flowers" in prompt
    assert "Finalise Setup" in prompt


def test_greet_prompt_unknown_step_raises():
    import pytest
    with pytest.raises(ValueError):
        get_greet_prompt(99, "X", "Y", "Z")
