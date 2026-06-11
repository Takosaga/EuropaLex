"""Tests for TextEngine — English text generation via Nemotron."""

from core.engine import TextEngine
from core.types import CEFRLevel


def test_build_generation_prompt():
    """TextEngine builds correct prompt for Nemotron generation mode."""
    engine = TextEngine.__new__(TextEngine)  # skip __init__
    engine.model_path = "/dev/null"
    engine.device = "cuda"

    result = engine._build_generation_prompt(
        scenario="ordering coffee",
        cefr_level=CEFRLevel.B1,
        batch_size=3,
    )

    assert "ordering coffee" in result
    assert "B1" in result
    assert "3" in result
    assert "one sentence per line" in result.lower()
    assert "no numbering" in result.lower()
    assert "No explanations" in result


def test_build_translation_prompt():
    """TextEngine builds correct prompt for translation mode."""
    engine = TextEngine.__new__(TextEngine)  # skip __init__
    engine.model_path = "/dev/null"
    engine.device = "cuda"

    result = engine._build_translation_prompt(
        texts=["Hello world", "Good morning"],
        scenario="",
        cefr_level=CEFRLevel.A2,
    )

    assert "Hello world" in result
    assert "Good morning" in result
    assert "A2" in result
    assert "Translate" in result
    assert "No explanations" in result


def test_generate_calls_llama_cli_subprocess():
    """TextEngine.generate() calls llama-cli with correct arguments."""
    import subprocess
    from unittest.mock import patch, MagicMock

    engine = TextEngine.__new__(TextEngine)  # skip __init__
    engine.model_path = "/path/to/model.gguf"
    engine.device = "cuda"

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Sentence one.\nSentence two.\nSentence three."
    mock_result.stderr = ""

    with patch.object(subprocess, "run", return_value=mock_result) as mock_run:
        result = engine.generate(
            texts=[],  # empty = generation mode (Nemotron)
            scenario="family members",
            cefr_level=CEFRLevel.B1,
            batch_size=3,
        )

    assert len(result.generated_texts) == 3
    assert result.generated_texts[0] == "Sentence one."

    # Verify llama-cli was called with correct args
    call_args = mock_run.call_args
    assert call_args[0][0][0] == "llama-cli"
    assert "-m" in call_args[0][0]
    assert str(engine.model_path) in call_args[0][0]
    assert "-n" in call_args[0][0]
    assert "512" in call_args[0][0]


def test_generate_raises_on_subprocess_failure():
    """TextEngine.generate() raises RuntimeError on non-zero exit."""
    import subprocess
    from unittest.mock import patch, MagicMock

    engine = TextEngine.__new__(TextEngine)
    engine.model_path = "/path/to/model.gguf"
    engine.device = "cuda"

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "model not found"

    with patch.object(subprocess, "run", return_value=mock_result):
        try:
            engine.generate(
                texts=[],
                scenario="test",
                cefr_level=CEFRLevel.B1,
                batch_size=1,
            )
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "llama-cli failed" in str(e)


if __name__ == "__main__":
    test_build_generation_prompt()
    print("PASS: build_generation_prompt")
    test_build_translation_prompt()
    print("PASS: build_translation_prompt")
    test_generate_calls_llama_cli_subprocess()
    print("PASS: generate calls subprocess")
    test_generate_raises_on_subprocess_failure()
    print("PASS: generate raises on failure")
    print("All tests passed.")
