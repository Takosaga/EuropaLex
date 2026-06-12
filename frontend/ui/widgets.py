# EuropaLex Frontend UI Components
# Custom styled Gradio widget wrappers


def create_toggle(label: str, value: bool = True, elem_id: str = "") -> "gr.Checkbox":
    """Create a styled toggle checkbox for media options.

    Args:
        label: Display label with emoji (e.g., '🖼️ Images').
        value: Default checked state.
        elem_id: Optional Gradio element ID.

    Returns:
        Configured gr.Checkbox instance.
    """
    import gradio as gr

    return gr.Checkbox(
        label=label,
        value=value,
        elem_id=elem_id if elem_id else "toggle-" + label.lower().replace(" ", "-").replace("🖼️", "img").replace("🔊", "audio"),
    )


def create_voice_dropdown(default_voice: str = "female, young adult") -> "gr.Dropdown":
    """Create a voice selection dropdown for TTS audio generation.

    Six presets mapped to OmniVoice instruct strings (gender × age).
    Ordered by gender first, then age from oldest to youngest.

    Args:
        default_voice: Default OmniVoice instruct string.

    Returns:
        Configured gr.Dropdown with 6 voice presets.
    """
    import gradio as gr

    choices = [
        "Female — Middle-Aged",
        "Female — Young Adult",
        "Female — Teenager",
        "Male — Middle-Aged",
        "Male — Young Adult",
        "Male — Teenager",
    ]

    return gr.Dropdown(
        label="Voice",
        choices=choices,
        value=default_voice,
        elem_id="voice-dropdown",
    )
