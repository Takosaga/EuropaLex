# EuropaLex — Gradio Frontend Demo Design

**Date:** 2026-06-08
**Scope:** Frontend-only implementation with mock data. No backend connection.
**Goal:** Interactive Gradio UI runnable locally via `uv sync && python app.py` to preview the visual design before backend integration.

---

## 1. Overview

Build a fully interactive Gradio frontend for EuropaLex that renders flashcard widgets on a warm wood-grain desk background. All card data is hardcoded mock content — no model inference, no API calls, no Anki sync. The purpose is to validate the visual design and user experience before wiring up the backend pipeline.

---

## 2. UI Layout (3 Sections)

### Section 1 — Input Panel (top)
- **Scenario input:** `gr.Textbox` placeholder "e.g., ordering coffee"
- **CEFR level:** `gr.Dropdown` with options `[A0, A1, A2, B1, B2, C1, C2]`, default `B1`
- **Batch size:** `gr.Slider` range 1–10, default 3
- **Generate button:** `gr.Button("Generate Cards")`

### Section 2 — Card Gallery (middle)
Cards rendered as styled Gradio `HTML` blocks. Each card displays:
- Front text (target language, bold, larger font)
- Back text (source language, muted gray, smaller)
- Audio play button (circular placeholder icon, non-functional)
- Image placeholder (gray box with dashed border, "🖼️" emoji)

Cards have slight CSS rotation (−3° to +3°) for a natural "spread on desk" feel.

### Section 3 — Export Bar (bottom)
Three buttons: **Export .apkg**, **Export CSV**, **Sync to Anki**. All disabled with grayed-out styling and hover tooltip: "Demo mode — requires backend connection".

---

## 3. Mock Data

Hardcoded in `app.py` as a dict keyed by CEFR level:

```
A0 set: ["Es esmu bērns.", "Šī ir māja.", "Es mīlu savu ģimeni."]
       → ["I am a child.", "This is a house.", "I love my family."]

B1 set (default): ["Es gribētu izdzert kafiju.", "Vai jūs varat man palīdzēt?", "Cik daudz maksā šis?"]
                 → ["I would like to drink coffee.", "Can you help me?", "How much does this cost?"]

Other levels: fallback to B1 set for demo purposes.
```

Each card includes placeholder `audio_path=None` and `image_path=None`.

On Generate click: cards for the selected batch size appear instantly from the appropriate mock set.

---

## 4. Styling & Theming

### Background — Warm Wood Grain (CSS-only, Option A)
- Base: diagonal gradient simulating wood grain (`linear-gradient(135deg, #8B6F47, #A0845C, #7A5E3A, #96784E)`)
- Texture overlay: repeating linear gradients (horizontal + vertical lines at fine intervals for wood grain pattern)
- Lighting: radial gradient highlight at top-center simulating overhead lamp light on the desk surface

### App Container
- Semi-transparent white card (`rgba(255, 250, 240, 0.92)`) with `backdrop-filter: blur(4px)` for frosted glass effect
- Rounded corners, subtle inner shadow

### Flashcard Widget
- White/cream background (`#fffef9`), border-radius 8px
- Drop shadow: `0 2px 6px rgba(0,0,0,0.15)` for depth against wood
- Border: thin warm tone (`#e8dcc8`)
- Front text: bold, 1.2em, dark brown (`#2a1f0f`)
- Back text: lighter weight, 0.95em, muted gray-brown (`#6b5e4a`), separated by dotted line
- Media buttons: circular, cream fill (`#f0e6d2`), subtle shadow

### Disabled Export Buttons
- Background: `#d4c5a9`, text color: `#8b7355`
- Opacity: 0.6, text-decoration: line-through
- Cursor: default (not pointer)

---

## 5. File Structure Changes

```
EuropaLex/
├── app.py                    # ← Rewritten: Gradio entry point + mock data
├── frontend/
│   ├── css/
│   │   └── custom.css        # ← Populated: wood grain background + card styling
│   └── ui/
│       ├── cards.py          # ← Kept as stub (future use)
│       └── widgets.py        # ← Kept as stub (future use)
├── pyproject.toml            # ← Updated: add gradio + pyyaml dependencies
└── requirements.txt          # ← Updated to match
```

No new files created. Existing stub files preserved for future backend integration.

---

## 6. Dependencies

**`pyproject.toml` additions:**
- `gradio>=4.0.0` — frontend framework
- `pyyaml>=6.0` — config parsing (for future use, added now to avoid later changes)

**Run locally:**
```bash
uv sync          # installs deps into .venv
python app.py    # launches Gradio on localhost:7860
```

---

## 7. What This Does NOT Include

- No backend pipeline calls (text generation, TTS, image gen)
- No actual export functionality (.apkg, CSV)
- No Anki tunnel sync
- No model loading or inference
- No A0 curated word list (mock data only)
- No error handling for missing models

These are deferred to the backend integration phase.

---

## 8. Success Criteria

1. `uv sync && python app.py` launches without errors
2. Gradio UI renders with warm wood grain background visible behind the app container
3. Input panel accepts user input (scenario text, CEFR selection, batch size)
4. Clicking Generate instantly displays mock flashcard widgets in the gallery
5. Cards show front/back text, audio placeholder, image placeholder
6. Export buttons are visible but disabled with demo-mode tooltip
7. Custom CSS is applied: card styling, wood grain background, frosted glass container
