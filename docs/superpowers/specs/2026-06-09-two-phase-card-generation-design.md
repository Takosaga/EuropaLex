# Two-Phase Card Generation Design

**Date:** 2026-06-09  
**Status:** Approved  
**Project:** EuropaLex — Gradio Flashcard Frontend

## Problem Statement

The current frontend has a single "Generate Cards" button that performs text generation, image generation, and audio generation in one continuous flow. The user wants to separate text generation from media generation so they can review the generated English text before committing to translations, images, and audio.

## Solution: Two-Phase Sequential Generation

Split card generation into two distinct phases with separate buttons and clear state transitions.

---

## UI Layout

```
┌─────────────────────────────────────┐
│  EuropaLex                          │
│  Generate Anki flashcards...        │
│                                     │
│  ─── Input Controls ─────────────── │
│  [Scenario/Topic textbox            │
│   CEFR Level dropdown               │
│   Number of Cards slider]           │
│                                     │
│  [Generate Text]                    │
│  ┌──────┐  ┌──────┐  ┌──────┐     │
│  │ EN   │  │ EN   │  │ EN   │     │
│  │ ---  │  │ ---  │  │ ---  │     │
│  └──────┘  └──────┘  └──────┘     │
│                                     │
│  🖼️ Images  [toggle] ← disabled     │
│  🔊 Audio   [toggle] ← disabled     │
│                                     │
│  [Generate Cards] ← disabled        │
│                                     │
│  [.apkg] [.csv] [Sync to Anki]     │
└─────────────────────────────────────┘
```

**Key changes from current layout:**
- "Generate Text" button added between input controls and card display area
- Card display area positioned immediately below "Generate Text", before toggles
- Toggles and "Generate Cards" button moved below the card area
- Progress bar appears after cards are rendered, not between buttons and cards

---

## State Flow

Three states control button visibility, toggle interactivity, and card content:

| State | Generate Text | Toggles | Generate Cards | Cards Display |
|-------|--------------|---------|----------------|---------------|
| **Idle** (initial) | Active, clickable | Disabled | Disabled | Empty / placeholder |
| **Text Generated** | Hidden or disabled | Disabled | Active, clickable | English text + dashed placeholder back |
| **Media Complete** | Hidden | Enabled (based on user choice) | Hidden | Full cards with EN, translations, images, audio |

### State Transitions

1. **Idle → Text Generated:** User clicks "Generate Text"
2. **Text Generated → Media Complete:** User adjusts toggles if needed, clicks "Generate Cards"
3. **Any state → Idle:** User changes scenario, CEFR level, or batch size (resets everything)

---

## Component Changes

### 1. `app.py` — Main Entry Point

**Split generation logic into two functions:**

- `generate_text_async(scenario, cefr_level, batch_size)` — Yields `(progress_html, card_output_html)` tuples. Generates English text from mock data, renders cards with placeholder back side.
- `generate_media_async(cards_data, include_images, include_audio)` — Takes existing card data, adds translations/images/audio, yields updated card HTML.

**Wire up new button events:**

```python
generate_text_btn.click(
    fn=generate_text_async,
    inputs=[scenario_input, cefr_dropdown, batch_slider],
    outputs=[progress_html, card_output],
)

generate_cards_btn.click(
    fn=generate_media_async,
    inputs=[card_state_ref, images_toggle, audio_toggle],
    outputs=[progress_html, card_output],
)
```

### 2. `frontend/ui/cards.py` — Card Rendering

**Add `placeholder_back` parameter to `render_card_html()`:**

```python
def render_card_html(card_data, include_image=False, include_audio=False, rotation=0.0, placeholder_back=True):
    # When placeholder_back=True: renders dashed line instead of translation text
    # When placeholder_back=False: renders actual back-text from card_data["back"]
```

**Update `generate_cards_html()` to accept and pass through `placeholder_back`.**

### 3. `frontend/ui/widgets.py` — Toggle Helper

**Add optional `interactive` parameter:**

```python
def create_toggle(label, value=True, elem_id="", interactive=True):
    # When interactive=False: renders with CSS opacity reduction
    # Gradio checkboxes don't have a built-in disabled state, so use CSS class
```

### 4. `frontend/css/custom.css` — Styling

**New classes:**

- `.btn-disabled` — Greyed-out button styling (opacity 0.5, cursor not-allowed)
- `.toggle-disabled` — Disabled toggle styling (opacity 0.5)
- `.card-placeholder-back` — Dashed/empty placeholder line for pending translation

---

## Data Flow

```
User inputs (scenario, level, batch)
        │
        ▼
generate_text_async()
        │
        ├── Reads MOCK_CARDS[cefr_level]
        ├── Selects top N cards
        └── Yields: cards with English text + placeholder back
                │
                ▼
        Cards rendered in display area
                │
                ▼
User reviews text, adjusts toggles if needed
                │
                ▼
generate_media_async(existing_cards, images_toggle, audio_toggle)
                │
                ├── Replaces placeholder back with actual translation
                ├── Adds image placeholders if include_images=True
                └── Adds audio buttons if include_audio=True
                        │
                        ▼
                Cards rendered with full media
```

---

## Error Handling

- **Empty scenario input:** Show warning message below buttons. Card area remains unchanged. User can retry.
- **Generation failure at any phase:** Progress bar shows error state (red color). "Generate Text" button reappears for retry.
- **Missing mock data for CEFR level:** Display friendly message in card area: "No cards available for this level."
- **User changes parameters mid-flow:** All states reset to Idle. Cards clear, both buttons become active/disabled appropriately.

---

## Edge Cases

1. **User changes scenario/level/batch after text generation** → "Generate Text" reappears, cards reset to empty
2. **User clicks "Generate Cards" without adjusting toggles** → Uses current toggle states (respects user's choice)
3. **User generates text but never clicks "Generate Cards"** → Cards remain in text-only state indefinitely
4. **Batch size larger than available mock data** → Shows all available cards, no error

---

## Files Modified

| File | Change Type | Description |
|------|-------------|-------------|
| `app.py` | Modify | Split generation into two functions, wire new button events |
| `frontend/ui/cards.py` | Modify | Add `placeholder_back` parameter to card rendering |
| `frontend/ui/widgets.py` | Modify | Add `interactive` parameter to toggle creation |
| `frontend/css/custom.css` | Modify | Add disabled styling classes |

No new files created.

---

## Non-Goals

- Inline editing of generated English text on cards (future enhancement)
- Three-phase generation (text → translate → media as separate steps)
- Backend API integration (remains mock data for now)
