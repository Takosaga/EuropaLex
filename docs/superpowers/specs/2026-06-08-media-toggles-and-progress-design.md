# Media Toggles and Progress Bar — Design Spec

**Date:** 2026-06-08
**Status:** Approved
**Approach:** Split card rendering into `frontend/ui/cards.py`

---

## 1. Problem Statement

The current Gradio frontend renders flashcards with always-visible image placeholders and audio buttons, regardless of user preference. There is no feedback during generation. The user needs:

1. Toggle switches to enable/disable images and audio on cards
2. Cards that adapt their size based on which media types are enabled
3. A progress bar showing sequential generation phases (text → images → audio)

---

## 2. Architecture

Three modules with clear responsibilities:

| Module | Responsibility |
|--------|---------------|
| `app.py` | UI orchestration — reads toggle states, drives generation flow, updates progress |
| `frontend/ui/cards.py` | Card HTML rendering — conditional element inclusion based on toggle booleans |
| `frontend/ui/widgets.py` | UI helpers — factory functions for consistent toggle components |

Existing modules unchanged: `frontend/css/custom.css`, mock data in `app.py`.

---

## 3. Toggle UI

### Placement
Two `gr.Checkbox` toggles in a sub-row within the input panel, between the existing inputs (scenario/level/batch) and the generate button.

### Toggles
- **Images toggle** — `value=True` (on by default)
- **Audio toggle** — `value=False` (off by default)
- Each has a label with emoji icon: "🖼️ Images" / "🔊 Audio"

### Visual layout
```
┌─────────────────────────────────────────────────────────┐
│ Scenario: [text input......]  Level: [B1 ▼]  Cards: [3]│
│                                                         │
│   🖼️ Images   ☑          🔊 Audio   ☐                 │
│                                                         │
│              [Generate Cards]                           │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Progress Bar

### Behavior
- Single progress bar with status text underneath
- Appears below the generate button during generation
- Auto-hides when generation completes
- Uses Gradio streaming outputs (`yield` generator) for incremental updates

### Phases and weights
| Phase | Status text | Bar weight | Triggered when |
|-------|------------|------------|----------------|
| Text generation | "Generating text..." | 0–30% | Always |
| Image generation | "Generating images..." | 30–80% | Images toggle ON |
| Audio generation | "Audio generation..." | 80–100% | Audio toggle ON |

If a phase's media is toggled OFF, that phase is skipped and remaining phases re-scale proportionally.

### Styling
- Light tan background (`#f0e8d6`)
- Brown gradient fill matching the generate button palette
- Status text in warm brown (`#6b5e4a`), 0.8em font size

---

## 5. Card Rendering

### Function signature (cards.py)
```python
def render_card_html(card_data: dict, include_image: bool, include_audio: bool, rotation: float = 0.0) -> str
```

### Adaptive card dimensions
| Media enabled | Width | Min-height | Elements rendered |
|--------------|-------|------------|-------------------|
| Text only | 150px | 80px | Front text, back text |
| Text + Image | 170px | 130px | + image placeholder div (40px) |
| Text + Audio | 170px | 120px | + audio button row |
| Text + Image + Audio | 180px | 160px | + image placeholder + audio buttons |

### Conditional elements
- **Image placeholder:** `<div class="img-placeholder">` — only when `include_image=True`
- **Audio button:** `<span class="media-btn">▶</span>` — only when `include_audio=True`
- Existing hover animation, rotation, and border styling preserved across all modes

---

## 6. Data Flow

```
User clicks "Generate Cards"
    │
    ├─ app.py reads: scenario, cefr_level, batch_size, images_toggle, audio_toggle
    │
    ├─ generate_cards_async() yields progress updates:
    │     yield (progress_html_30%,  card_text_only)   → "Generating text..."
    │     yield (progress_html_80%,  card_with_images) → "Generating images..."
    │     yield (progress_html_100%, card_full)        → "Done!"
    │
    ├─ cards.py.render_card_html() called per card with toggle booleans
    │
    └─ Progress bar auto-hides after final yield
```

### Incremental updates
Cards update visually after each phase completes:
1. After text phase: user sees text-only cards (fast feedback)
2. After image phase: cards update to include image placeholders
3. After audio phase: cards show final state with all enabled media

### Data immutability
`MOCK_CARDS` in `app.py` remains unchanged. Toggle booleans control rendering only, not data selection or filtering.

---

## 7. Error Handling

- Empty toggle states (neither on) → defaults to text-only mode
- Invalid card data → falls back to "No cards available" message (existing behavior)
- Generation errors → progress bar shows error state with red styling, card output shows error message

---

## 8. Testing Strategy

- **Unit tests for `cards.py`:** Verify `render_card_html()` produces correct HTML for all four media combinations
- **Integration test in `app.py`:** Verify toggle state changes are reflected in card output
- **Progress bar test:** Verify streaming yields produce correct percentage updates

---

## 9. Out of Scope

- Actual image generation (placeholder remains)
- Actual audio synthesis (button remains non-functional)
- Per-card media toggles (global toggles only)
- Export button functionality (unchanged from demo state)
- Animation for progress bar transitions
