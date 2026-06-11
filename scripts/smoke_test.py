# EuropaLex Smoke Test
# End-to-end pipeline test with mock models (no actual inference)

import sys


def main():
    errors = []

    # Test 1: Import core types
    try:
        from core.types import CardData, CEFRLevel, TextResult, AudioResult, ImageResult, EngineConfig
        print("✓ core.types imports OK")
    except Exception as e:
        errors.append(f"core.types import failed: {e}")

    # Test 2: Import engine modules
    try:
        from core.engine import MiniCPMTextEngine, LlamaCppTextEngine, TTSEngine, ImageGenEngine, EnginePool
        print("✓ core.engine imports OK")
    except Exception as e:
        errors.append(f"core.engine import failed: {e}")

    # Test 3: Validate CardData construction
    try:
        card = CardData(text="Hello", translation="Sveiki", cefr_level=CEFRLevel.A1)
        assert card.text == "Hello"
        assert card.translation == "Sveiki"
        assert card.cefr_level == CEFRLevel.A1
        print("✓ CardData validation OK")
    except Exception as e:
        errors.append(f"CardData validation failed: {e}")

    # Test 4: Validate TextResult construction
    try:
        result = TextResult(generated_texts=["Sveiki", "Labdien"])
        assert len(result.generated_texts) == 2
        print("✓ TextResult validation OK")
    except Exception as e:
        errors.append(f"TextResult validation failed: {e}")

    # Test 5: Validate AudioResult construction (never None — default_factory=list)
    try:
        result = AudioResult(audio_paths=["/path/audio_0.wav", "/path/audio_1.wav"])
        assert len(result.audio_paths) == 2
        print("✓ AudioResult validation OK")
    except Exception as e:
        errors.append(f"AudioResult validation failed: {e}")

    # Test 6: Validate ImageResult construction (never None — default_factory=list)
    try:
        result = ImageResult(image_paths=["/path/image_0.png"])
        assert len(result.image_paths) == 1
        print("✓ ImageResult validation OK")
    except Exception as e:
        errors.append(f"ImageResult validation failed: {e}")

    # Test 7: Validate TextResult.validate_and_parse gate
    try:
        from core.types import ValidationError
        result = TextResult.validate_and_parse("Hello\nWorld", expected_count=2)
        assert len(result.generated_texts) == 2
        assert result.generated_texts[0] == "Hello"
        # Strips thinking tags
        raw_with_tags = "<thinking>reasoning here</thinking>\nFoo\nBar"
        result2 = TextResult.validate_and_parse(raw_with_tags, expected_count=2)
        assert len(result2.generated_texts) == 2
        assert result2.generated_texts[0] == "Foo"
        # Raises on count mismatch
        try:
            TextResult.validate_and_parse("One\nTwo\nThree", expected_count=2)
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass  # expected
        print("✓ TextResult.validate_and_parse gate OK")
    except Exception as e:
        errors.append(f"TextResult validation gate failed: {e}")

    # Test 8: Import frontend modules
    try:
        from frontend.ui.cards import render_card_html, generate_cards_html, generate_progress_html
        from frontend.ui.widgets import create_toggle
        print("✓ frontend.ui imports OK")
    except Exception as e:
        errors.append(f"frontend.ui import failed: {e}")

    # Test 9: Import app module
    try:
        import app
        print("✓ app module loads OK")
    except Exception as e:
        errors.append(f"app module load failed: {e}")

    if errors:
        print(f"\n❌ {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n✅ All smoke tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
