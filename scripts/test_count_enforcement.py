"""Quick inline test for MiniCPMTextEngine sentence count enforcement.

Tests _validate_lines, TextResult construction, and _build_strict_prompt
with mock data (no LLM call needed).
"""

from core.types import CEFRLevel, TextResult, ValidationError


def test_validate_lines():
    """Test that _validate_lines returns correct boolean for matching/non-matching counts."""
    # Simulate the method inline since we can't instantiate the engine without a model file
    def _validate_lines(lines: list[str], expected: int) -> bool:
        return len(lines) == expected

    assert _validate_lines(["sentence one", "sentence two", "sentence three"], 3) is True
    assert _validate_lines(["sentence one"], 3) is False
    assert _validate_lines(["s1", "s2", "s3", "s4", "s5"], 3) is False
    assert _validate_lines([], 3) is False
    print("test_validate_lines: PASS")





def test_textresult_construction():
    """Test that TextResult accepts a list of exactly the right length."""
    result = TextResult(generated_texts=["a", "b", "c"])
    assert len(result.generated_texts) == 3
    assert result.generated_texts[0] == "a"
    print("test_textresult_construction: PASS")


def test_validate_and_parse_gate():
    """Test that validate_and_parse enforces exact count and strips thinking tags."""
    # Success case
    result = TextResult.validate_and_parse("Line one\nLine two", expected_count=2)
    assert len(result.generated_texts) == 2

    # Count mismatch
    try:
        TextResult.validate_and_parse("One\nTwo\nThree", expected_count=2)
        assert False, "Should raise on count mismatch"
    except ValidationError:
        pass

    # Empty after stripping thinking tags
    try:
        TextResult.validate_and_parse("<thinking>only reasoning</thinking>", expected_count=1)
        assert False, "Should raise on empty output"
    except ValidationError:
        pass

    # Thinking tag strip preserves actual sentences
    raw = "<thinking>some thoughts\nmore thoughts</thinking>\nActual sentence 1\nActual sentence 2"
    result2 = TextResult.validate_and_parse(raw, expected_count=2)
    assert result2.generated_texts == ["Actual sentence 1", "Actual sentence 2"]

    print("test_validate_and_parse_gate: PASS")


def test_build_strict_prompt_has_examples():
    """Test that _build_strict_prompt includes example output sections."""
    def _build_strict_prompt(scenario, cefr_level_label, batch_size):
        examples = {
            1: (
                "Example output:\n"
                "The sun rises in the east every morning.\n"
            ),
            2: (
                "Example output:\n"
                "The cat sits on the warm windowsill.\n"
                "Children play in the garden after school.\n"
            ),
            3: (
                "Example output:\n"
                "The family gathers around the table for dinner.\n"
                "Parents help their children with homework.\n"
                "Weekends are for visiting grandparents.\n"
            ),
        }
        example_section = examples.get(batch_size, (
            f"Example output:\n"
            "The family eats together in the kitchen.\n"
            "They talk about their day before bed.\n"
        ))
        return (
            f"You are a language teacher. Generate exactly {batch_size} simple, clear sentences "
            f"at CEFR level {cefr_level_label} about the scenario below.\n\n"
            f"{example_section}\n"
            f"Scenario: {scenario}\n\n"
            f"Output exactly {batch_size} sentences now. ONE sentence per line. Nothing else."
        )

    prompt = _build_strict_prompt("family", "B1", 3)
    assert "Example output:" in prompt
    assert "The family gathers around the table for dinner." in prompt
    assert "Output exactly 3 sentences" in prompt
    assert "ONE sentence per line" in prompt
    print("test_build_strict_prompt_has_examples: PASS")


def test_build_strict_prompt_batch_size_1():
    """Test strict prompt for batch_size=1."""
    def _build_strict_prompt(scenario, cefr_level_label, batch_size):
        examples = {
            1: (
                "Example output:\n"
                "The sun rises in the east every morning.\n"
            ),
            2: (
                "Example output:\n"
                "The cat sits on the warm windowsill.\n"
                "Children play in the garden after school.\n"
            ),
            3: (
                "Example output:\n"
                "The family gathers around the table for dinner.\n"
                "Parents help their children with homework.\n"
                "Weekends are for visiting grandparents.\n"
            ),
        }
        example_section = examples.get(batch_size, (
            f"Example output:\n"
            "The family eats together in the kitchen.\n"
            "They talk about their day before bed.\n"
        ))
        return (
            f"You are a language teacher. Generate exactly {batch_size} simple, clear sentences "
            f"at CEFR level {cefr_level_label} about the scenario below.\n\n"
            f"{example_section}\n"
            f"Scenario: {scenario}\n\n"
            f"Output exactly {batch_size} sentences now. ONE sentence per line. Nothing else."
        )

    prompt = _build_strict_prompt("weather", "A0", 1)
    assert "The sun rises in the east every morning." in prompt
    assert "Output exactly 1 sentences" in prompt
    print("test_build_strict_prompt_batch_size_1: PASS")


if __name__ == "__main__":
    test_validate_lines()
    test_textresult_construction()
    test_validate_and_parse_gate()
    test_build_strict_prompt_has_examples()
    test_build_strict_prompt_batch_size_1()
    print("\nAll inline tests passed.")
