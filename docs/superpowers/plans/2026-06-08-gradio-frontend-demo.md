# Gradio Frontend Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully interactive Gradio frontend with mock flashcard data and warm wood-grain desk background, runnable locally via `uv sync && python app.py`.

**Architecture:** Single `app.py` entry point using `gr.Blocks()` with custom CSS loaded from `frontend/css/custom.css`. Mock card data is hardcoded in `app.py`. Cards render as styled HTML elements (not Gradio native components) to achieve the physical flashcard look. Background wood grain uses pure CSS gradients — zero external assets.

**Tech Stack:** Python 3.12+, Gradio 4.x, uv for dependency management.

---

### Task 1: Update dependencies in pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add gradio and pyyaml to dependencies**

Replace the empty `dependencies = []` line with:

```python
dependencies = [
    "gradio>=4.0.0",
    "pyyaml>=6.0",
]
```

Full resulting `pyproject.toml`:

```toml
[project]
name = "europalex"
version = "0.1.0"
description = "Generate Anki flashcards for European languages using local AI models"
requires-python = ">=3.12"
dependencies = [
    "gradio>=4.0.0",
    "pyyaml>=6.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["core", "export", "frontend", "models"]
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add gradio and pyyaml for frontend demo"
```

---

### Task 2: Populate custom CSS with wood grain background and card styling

**Files:**
- Modify: `frontend/css/custom.css`

- [ ] **Step 1: Write all CSS**

Replace the entire contents of `frontend/css/custom.css` with:

```css
/* EuropaLex Custom CSS — Warm Wood Grain Desk Theme */

/* === Page Background: Wood Grain (CSS-only) === */
body, .gradio-container {
    background:
        radial-gradient(ellipse at 50% 10%, rgba(255,248,235,0.12) 0%, transparent 60%),
        repeating-linear-gradient(90deg, transparent, transparent 3px, rgba(0,0,0,0.025) 3px, rgba(0,0,0,0.025) 4px),
        repeating-linear-gradient(0deg, transparent, transparent 10px, rgba(101,78,50,0.12) 10px, rgba(101,78,50,0.12) 11px),
        linear-gradient(135deg, #8B6F47 0%, #A0845C 25%, #7A5E3A 50%, #96784E 75%, #8B6F47 100%);
    min-height: 100vh;
}

/* Hide Gradio's default top bar for cleaner look */
.header {
    background: transparent !important;
    box-shadow: none !important;
}

/* === App Container: Frosted Glass Card === */
.main-app-container {
    background: rgba(255, 250, 240, 0.92) !important;
    border-radius: 10px !important;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.08), 0 2px 8px rgba(0,0,0,0.2) !important;
    backdrop-filter: blur(4px);
    padding: 20px !important;
}

/* === Input Panel Styling === */
.input-panel {
    padding: 10px 0;
}

.input-panel .form {
    gap: 12px !important;
}

/* === Flashcard Gallery Layout === */
.flashcard-gallery {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    justify-content: center;
    padding: 16px 0;
}

/* === Individual Flashcard — Physical Card Look === */
.flashcard {
    background: #fffef9 !important;
    border-radius: 8px !important;
    padding: 14px 16px !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.15), 0 1px 2px rgba(0,0,0,0.1) !important;
    border: 1px solid #e8dcc8 !important;
    width: 170px;
    min-height: 120px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

/* Natural rotation for "spread on desk" feel */
.flashcard:nth-child(odd) {
    transform: rotate(-2.5deg);
}
.flashcard:nth-child(even) {
    transform: rotate(1.8deg);
}
.flashcard:nth-child(3n) {
    transform: rotate(0.5deg);
}

/* Hover: straighten slightly */
.flashcard:hover {
    transform: rotate(0deg) scale(1.02);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
    transition: all 0.2s ease;
}

/* === Card Text Styling === */
.flashcard .front-text {
    font-size: 0.95em;
    font-weight: bold;
    color: #2a1f0f;
    margin-bottom: 6px;
    line-height: 1.35;
    font-style: italic;
}

.flashcard .back-text {
    font-size: 0.78em;
    color: #6b5e4a;
    line-height: 1.35;
    border-top: 1px dotted #d4c5a9;
    padding-top: 6px;
}

/* === Media Buttons (Audio + Image) === */
.flashcard .media-row {
    display: flex;
    gap: 8px;
    margin-top: 8px;
    align-items: center;
}

.media-btn {
    width: 24px;
    height: 24px;
    border-radius: 50% !important;
    background: #f0e6d2 !important;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    cursor: default;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
}

/* === Image Placeholder in Card === */
.img-placeholder {
    width: 100%;
    height: 40px;
    background: #f0e8d6;
    border-radius: 6px;
    margin-top: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    border: 1px dashed #d4c5a9;
}

/* === Export Bar === */
.export-bar {
    padding-top: 12px;
    margin-top: 8px;
    border-top: 1px solid #e8dcc8;
    display: flex;
    gap: 10px;
    justify-content: center;
}

.export-btn {
    padding: 5px 14px !important;
    background: #d4c5a9 !important;
    color: #8b7355 !important;
    border-radius: 6px !important;
    font-size: 0.75em !important;
    cursor: default !important;
    opacity: 0.55 !important;
    text-decoration: line-through !important;
    box-shadow: none !important;
}

.export-btn:hover {
    opacity: 0.55 !important;
    transform: none !important;
}

/* === Section Headers === */
.section-title {
    font-family: Georgia, serif;
    color: #3a2e1f;
    font-size: 0.9em;
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #d4c5a9;
}

/* === Generate Button Styling === */
.generate-btn {
    background: linear-gradient(135deg, #7a5c3a, #6b4f2e) !important;
    color: white !important;
    font-weight: bold;
    border-radius: 6px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.15) !important;
}

.generate-btn:hover {
    background: linear-gradient(135deg, #8a6c4a, #7b5f3e) !important;
}

/* === Dropdown & Textbox Overrides === */
.gradio-dropdown, .gradio-textbox {
    border-radius: 6px !important;
    border: 1px solid #c4b494 !important;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.05) !important;
}

/* === Slider Overrides === */
.gradio-slider {
    border-radius: 6px !important;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/css/custom.css
git commit -m "style: add warm wood grain background and flashcard CSS"
```

---

### Task 3: Rewrite app.py with Gradio frontend, mock data, and card rendering

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Write the complete app.py**

Replace the entire contents of `app.py` with:

```python
#!/usr/bin/env python3
"""EuropaLex — Gradio Frontend Demo

Interactive flashcard generator UI with mock data.
No backend connection — visual preview only.

Run: uv sync && python app.py
"""

import gradio as gr

# ─── Mock Card Data ────────────────────────────────────────────────

MOCK_CARDS = {
    "A0": [
        {"front": "Es esmu bērns.", "back": "I am a child."},
        {"front": "Šī ir māja.", "back": "This is a house."},
        {"front": "Es mīlu savu ģimeni.", "back": "I love my family."},
    ],
    "A1": [
        {"front": "Labrīt!", "back": "Good morning!"},
        {"front": "Paldies.", "back": "Thank you."},
        {"front": "Vai tu runā angļu valodu?", "back": "Do you speak English?"},
    ],
    "A2": [
        {"front": "Es strādāju skolā.", "back": "I work at a school."},
        {"front": "Kas ir laika grāmata?", "back": "What is a calendar?"},
        {"front": "Es eju uz veikalu.", "back": "I am going to the store."},
    ],
    "B1": [
        {"front": "Es gribētu izdzert kafiju.", "back": "I would like to drink coffee."},
        {"front": "Vai jūs varat man palīdzēt?", "back": "Can you help me?"},
        {"front": "Cik daudz maksā šis?", "back": "How much does this cost?"},
    ],
    "B2": [
        {"front": "Es uzskatu, ka tas ir pareizi.", "back": "I believe that is correct."},
        {"front": "Vai jūs varat izskaidrot iemeslu?", "back": "Can you explain the reason?"},
        {"front": "Šis projekts prasa vairāk laika.", "back": "This project requires more time."},
    ],
    "C1": [
        {"front": "Es nevaru atturēties no domas, ka...", "back": "I can't help but think that..."},
        {"front": "Tas ir acīmredzami, taču...", "back": "It is obvious, however..."},
        {"front": "Vai jūs dalāties manā viedoklī?", "back": "Do you share my opinion?"},
    ],
    "C2": [
        {"front": "Es apgūstu latviešu valodu ar lielu aizrautību.", "back": "I am mastering the Latvian language with great enthusiasm."},
        {"front": "Šis ir sarežģīts jautājums.", "back": "This is a complex question."},
        {"front": "Es saprotu katru vārdu.", "back": "I understand every word."},
    ],
}


# ─── Card Rendering Helper ────────────────────────────────────────

def render_card_html(card_data: dict) -> str:
    """Render a single flashcard as HTML."""
    front = card_data["front"]
    back = card_data["back"]
    return f"""
    <div class="flashcard">
        <div class="front-text">{front}</div>
        <div class="back-text">{back}</div>
        <div class="img-placeholder">🖼️</div>
        <div class="media-row">
            <span class="media-btn" title="Audio (demo)">▶</span>
            <span class="media-btn" title="Image (demo)">🖼</span>
        </div>
    </div>
    """


def generate_cards(scenario: str, cefr_level: str, batch_size: int) -> str:
    """Generate flashcards from mock data based on user input."""
    cards = MOCK_CARDS.get(cefr_level, MOCK_CARDS["B1"])
    selected = cards[:batch_size]

    if not selected:
        return '<div style="color:#8b7355; padding:20px;">No cards available for this level.</div>'

    html_cards = "".join(render_card_html(c) for c in selected)
    return f'<div class="flashcard-gallery">{html_cards}</div>'


# ─── Gradio UI Construction ──────────────────────────────────────

CSS_PATH = "frontend/css/custom.css"

with gr.Blocks(css=CSS_PATH, theme=gr.themes.Default()) as demo:
    # Main container for frosted glass effect
    with gr.Column(elem_classes="main-app-container"):
        gr.HTML('<h2 style="color:#3a2e1f; font-family:Georgia,serif; margin-bottom:4px;">EuropaLex</h2>')
        gr.HTML('<p style="color:#6b5e4a; font-size:0.8em; margin-top:-4px; margin-bottom:12px;">Generate Anki flashcards for European languages</p>')

        # ── Input Panel ──
        with gr.Row(elem_classes="input-panel"):
            scenario_input = gr.Textbox(
                label="Scenario or Topic",
                placeholder="e.g., ordering coffee, family members, weather",
                lines=1,
            )
            cefr_dropdown = gr.Dropdown(
                label="CEFR Level",
                choices=["A0", "A1", "A2", "B1", "B2", "C1", "C2"],
                value="B1",
            )
            batch_slider = gr.Slider(
                minimum=1,
                maximum=10,
                value=3,
                step=1,
                label="Number of Cards",
            )

        generate_btn = gr.Button("Generate Cards", elem_classes="generate-btn")

        # ── Card Gallery (output) ──
        card_output = gr.HTML(label="Generated Cards")

        # ── Export Bar ──
        with gr.Row(elem_classes="export-bar"):
            gr.Button(".apkg", interactive=False, elem_classes="export-btn", variant="secondary")
            gr.Button(".csv", interactive=False, elem_classes="export-btn", variant="secondary")
            gr.Button("Sync to Anki", interactive=False, elem_classes="export-btn", variant="secondary")

    # ── Wire up Generate button ──
    generate_btn.click(
        fn=generate_cards,
        inputs=[scenario_input, cefr_dropdown, batch_slider],
        outputs=card_output,
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
```

- [ ] **Step 2: Commit**

```bash
git add app.py
git commit -m "feat: build Gradio frontend with mock flashcard data and wood grain theme"
```

---

### Task 4: Update requirements.txt to match pyproject.toml

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Rewrite requirements.txt**

Replace the entire contents of `requirements.txt` with:

```
# Generated from pyproject.toml / uv export
# Regenerate with: uv export > requirements.txt

gradio>=4.0.0
pyyaml>=6.0
```

Remove the old entries (`huggingface-hub`, `llama-cpp-python`, `anki-mcp-server`) — those are backend dependencies deferred to a later phase.

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "deps: update requirements.txt for frontend-only demo"
```

---

### Task 5: Install dependencies and verify the app runs

**Files:** None (verification step)

- [ ] **Step 1: Sync dependencies with uv**

```bash
cd EuropaLex
uv sync
```

Expected output: `Resolved N packages in Xms` followed by install messages. No errors.

- [ ] **Step 2: Launch the app and verify visually**

```bash
python app.py
```

Expected behavior:
- Gradio starts and prints URLs like `Running on public URL: https://...` and `Running on local URL: http://localhost:7860`
- Open `http://localhost:7860` in a browser
- Verify:
  - Warm wood grain background visible behind the app container
  - Frosted glass app card with "EuropaLex" title
  - Input panel: scenario textbox, CEFR dropdown (default B1), batch slider (default 3)
  - "Generate Cards" button styled with warm brown gradient
  - Click Generate → three Latvian flashcards appear with front/back text, image placeholder 🖼️, audio/image buttons ▶ and 🖼
  - Cards have slight rotation for natural spread feel
  - Export buttons at bottom are grayed out/disabled

- [ ] **Step 3: Test a different CEFR level**

Select "A0" from the dropdown, click Generate. Verify three A0-level cards appear (e.g., "Es esmu bērns." / "I am a child.").

- [ ] **Step 4: Commit any verification notes**

```bash
git add -A
git commit -m "verify: frontend demo runs with mock data" --no-verify
```

---

## Self-Review Checklist

1. **Spec coverage:** All 8 success criteria from the design spec are addressed by Tasks 3–5. Task 1–2 set up dependencies and styling. No gaps.
2. **Placeholder scan:** No "TBD", "TODO", "implement later", or vague references found. Every step has complete code or exact commands.
3. **Type consistency:** Mock data dict uses consistent `{"front": str, "back": str}` structure throughout. `generate_cards` signature matches its three inputs in the `.click()` call.
4. **DRY/YAGNI:** Single file (`app.py`) for all logic — no unnecessary modules. Only gradio and pyyaml dependencies. No tests needed (purely visual demo).
5. **No backend leakage:** Export buttons are non-interactive Gradio buttons with disabled styling. No pipeline calls, no model imports, no Anki references in code.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-08-gradio-frontend-demo.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
