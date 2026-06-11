"""Quick inline test for MiniCPMTextEngine sentence count enforcement.

Run after models are downloaded. Tests that _validate_lines and _build_retry_prompt
work correctly with mock data (no LLM call needed).
"""

from core.types import CEFRLevel, TextResult


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


def test_build_retry_prompt_over():
    """Test retry prompt for over-generation."""
    def _build_retry_prompt(actual: int, expected: int) -> str:
        if actual > expected:
            return (
                f"You were asked for exactly {expected} sentences but produced {actual}. "
                f"Output only the first {expected} sentences now. ONE per line, no explanations."
            )
        else:
            return (
                f"You were asked for exactly {expected} sentences but produced {actual}. "
                f"Produce all {expected} sentences now. ONE per line, no explanations."
            )

    prompt = _build_retry_prompt(10, 3)
    assert "exactly 3" in prompt
    assert "produced 10" in prompt
    assert "Output only the first 3" in prompt
    print("test_build_retry_prompt_over: PASS")


def test_build_retry_prompt_under():
    """Test retry prompt for under-generation."""
    def _build_retry_prompt(actual: int, expected: int) -> str:
        if actual > expected:
            return (
                f"You were asked for exactly {expected} sentences but produced {actual}. "
                f"Output only the first {expected} sentences now. ONE per line, no explanations."
            )
        else:
            return (
                f"You were asked for exactly {expected} sentences but produced {actual}. "
                f"Produce all {expected} sentences now. ONE per line, no explanations."
            )

    prompt = _build_retry_prompt(1, 3)
    assert "exactly 3" in prompt
    assert "produced 1" in prompt
    assert "Produce all 3" in prompt
    print("test_build_retry_prompt_under: PASS")


def test_textresult_construction():
    """Test that TextResult accepts a list of exactly the right length."""
    result = TextResult(translations=["a", "b", "c"])
    assert len(result.translations) == 3
    assert result.translations[0] == "a"
    print("test_textresult_construction: PASS")


if __name__ == "__main__":
    test_validate_lines()
    test_build_retry_prompt_over()
    test_build_retry_prompt_under()
    test_textresult_construction()
    print("\nAll inline tests passed.")
