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
