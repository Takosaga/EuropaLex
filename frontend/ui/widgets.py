# EuropaLex Frontend UI Components
# Custom styled Gradio widget wrappers


def create_toggle(label: str, value: bool = True, elem_id: str = "", interactive: bool = True) -> "gr.Checkbox":
    """Create a styled toggle checkbox for media options.

    Args:
        label: Display label with emoji (e.g., '🖼️ Images').
        value: Default checked state.
        elem_id: Optional Gradio element ID.
        interactive: If False, apply disabled styling via CSS class wrapper.

    Returns:
        Configured gr.Checkbox instance.
    """
    import gradio as gr

    checkbox = gr.Checkbox(
        label=label,
        value=value,
        elem_id=elem_id if elem_id else "toggle-" + label.lower().replace(" ", "-").replace("🖼️", "img").replace("🔊", "audio"),
    )

    if not interactive:
        # Gradio doesn't have a native disabled checkbox, so apply CSS class
        checkbox.elem_classes = (checkbox.elem_classes or []) + ["europalex-toggle-disabled"]

    return checkbox
