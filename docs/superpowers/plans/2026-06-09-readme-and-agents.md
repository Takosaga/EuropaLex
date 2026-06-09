# README + AGENTS.md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-facing Workflow section and developer-facing Architecture section to the README, and create an AGENTS.md conventions guide for AI coding agents.

**Architecture:** Two documentation-only changes — enhance README.md in place by inserting new sections between existing content, and create a new AGENTS.md at repo root. No code changes.

**Tech Stack:** Markdown, Python project (EuropaLex)

---

### Task 1: Add Workflow section to README.md

**Files:**
- Modify: `README.md` — insert "Workflow" section after CEFR Levels

Insert the following section **after** the CEFR Levels section (at end of file):

```markdown
## Workflow

EuropaLex generates flashcards in two phases: text first, then media.

### Phase 1 — Generate Text

1. Enter a scenario or paste text in the input box
2. Select a CEFR level (`A0`–`C2`) from the dropdown
3. Set the batch size with the slider (number of cards to generate)
4. Click **Generate Text**
5. The app calls TildeOpen to produce English text and target-language translations for each card
6. Cards appear in the gallery with front (English) and back (translation) text

### Phase 2 — Generate Media

1. After Phase 1 completes, the **Images** and **Audio** toggles become active
2. Toggle on whichever media types you want (images, audio, or both)
3. Click **Generate Cards**
4. The app calls OmniVoice for text-to-speech and FLUX.2 for illustrative images
5. Media buttons appear on each card

### Export

1. Once cards are generated, click **Export to Anki** (`.apkg`) or **Export as CSV**
2. For power users: run `npx @ankimcp/anki-mcp-server --tunnel` locally and use the Sync to Anki button in the app

---
```

- [ ] **Step 1: Insert Workflow section into README.md**

Read the current `README.md`, find the end of the CEFR Levels section, and append the new Workflow section as shown above. Preserve all existing content exactly.

- [ ] **Step 2: Verify README.md renders correctly**

```bash
cat /home/takosaga/Projects/EuropaLex/README.md | head -120
```

Check that:
- All original sections are intact (intro, hackathon criteria, setup, model table, repo structure, CEFR levels)
- The new Workflow section appears after CEFR Levels
- Markdown headers use `##` for top-level sections
- No duplicated or missing content

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add README.md
git commit -m "docs: add Workflow section to README"
```

---

### Task 2: Add Architecture section to README.md

**Files:**
- Modify: `README.md` — insert "Architecture" section after Workflow section

Insert the following section **after** the Workflow section (between Workflow and the existing Repository Structure):

```markdown
## Architecture

EuropaLex is organized into five main modules:

| Module | Purpose |
|---|---|
| `core/` | Data types (`types.py`), inference engine protocol + implementations (`engine.py`), batch pipeline orchestrator (`pipeline.py`) |
| `frontend/` | Gradio 6 UI: styled toggles (`widgets.py`), card rendering and gallery layout (`cards.py`), custom CSS (`css/custom.css`) |
| `models/` | Hugging Face Hub model downloader — fetches models at runtime, no git submodules |
| `export/` | `.apkg` Anki package generator, CSV export, Anki tunnel sync via MCP server |
| `app.py` | Entry point — wires inputs to two-phase click handlers with progress tracking |

### Data Flow

```
User Input → [Gradio UI] → Inference Engine (TildeOpen) → Pipeline (batch: text→audio→image) → Card Gallery → Export (.apkg / .csv)
```

- **Inference:** `core/engine.py` defines the `InferenceEngine` protocol. Implementations (`LocalInference`, `ModalInference`) wrap llama.cpp or Modal-hosted endpoints.
- **Pipeline:** `core/pipeline.py` orchestrates batch generation — text first, then audio and images in parallel based on toggle state.
- **Frontend:** `frontend/ui/cards.py` renders individual cards as HTML with conditional media elements; `generate_cards_html()` layouts them in a flex gallery with natural rotation offsets.
- **Export:** `export/apkg_generator.py` builds Anki packages; `export/csv_export.py` writes tabular data; `export/anki_tunnel.py` communicates with the Anki MCP tunnel server.

---
```

- [ ] **Step 1: Insert Architecture section into README.md**

Read `README.md`, find the end of the Workflow section (the horizontal rule `---` after it), and append the new Architecture section as shown above. Preserve all existing content exactly.

- [ ] **Step 2: Verify README.md renders correctly**

```bash
cat /home/takosaga/Projects/EuropaLex/README.md | head -160
```

Check that:
- The Architecture section appears between Workflow and Repository Structure
- The data flow diagram is present
- All original sections remain intact
- No content was accidentally duplicated or removed

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add README.md
git commit -m "docs: add Architecture section to README"
```

---

### Task 3: Update Repository Structure in README.md

**Files:**
- Modify: `README.md` — update the Repository Structure code block to match current file layout

Replace the existing Repository Structure code block with this updated version:

```markdown
## Repository Structure

```
EuropaLex/
├── app.py                  # Entry point — Gradio UI wiring, two-phase generation handlers
├── pyproject.toml          # Project config (uv)
├── requirements.txt        # pip install dependencies
├── uv.lock                 # uv lock file
├── .gitignore
├── README.md               # This file
├── AGENTS.md               # AI agent conventions guide
├── core/                   # Shared business logic
│   ├── __init__.py
│   ├── types.py            # Card, CardData, CEFRLevel dataclasses
│   ├── engine.py           # InferenceEngine protocol + LocalInference/ModalInference
│   └── pipeline.py         # Batch generator: text → audio → image orchestrator
├── frontend/               # Gradio 6 UI
│   ├── __init__.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── widgets.py      # Styled toggle checkbox wrappers
│   │   └── cards.py        # Card rendering, gallery layout, progress bar
│   └── css/
│       └── custom.css      # Plain-white theme, card styling, disabled states
├── models/                 # Model management
│   ├── __init__.py
│   └── download_models.py  # HF Hub model downloader (runtime)
├── configs/                # Configuration
│   └── settings.yaml       # App settings, word lists
├── export/                 # Export formats
│   ├── __init__.py
│   ├── apkg_generator.py   # Anki .apkg package builder
│   ├── csv_export.py       # CSV export utility
│   └── anki_tunnel.py      # MCP tunnel sync for live Anki import
├── docs/                   # Design specs and implementation plans
│   └── superpowers/
│       ├── specs/          # Design specification documents
│       └── plans/          # Implementation plans
└── scripts/                # Utility scripts
    └── smoke_test.py       # Quick sanity check script
```
```

- [ ] **Step 1: Replace Repository Structure code block in README.md**

Read `README.md`, find the existing `## Repository Structure` header and its code block, replace with the updated version above. Everything before and after should remain unchanged.

- [ ] **Step 2: Verify README.md is correct**

```bash
cat /home/takosaga/Projects/EuropaLex/README.md | tail -60
```

Check that:
- The new structure reflects actual files (app.py, AGENTS.md mention, frontend/ui/, docs/superpowers/)
- No stale references remain (e.g., "Gradio UI code inside app.py" for frontend/)
- Structure tree is properly indented with `├──` and `└──`

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add README.md
git commit -m "docs: update Repository Structure to match current layout"
```

---

### Task 4: Create AGENTS.md — Project Overview and Code Structure

**Files:**
- Create: `AGENTS.md` at repo root

Write the first two sections of AGENTS.md:

```markdown
# EuropaLex — AI Agent Conventions

Guidelines for AI coding agents working on this codebase. Follow these conventions to produce changes that integrate cleanly.

## Project Overview

EuropaLex generates Anki-compatible flashcards for European languages using local AI models. It takes user input (text or scenario description), generates target-language translations at a selected CEFR level, and enriches cards with text-to-speech audio and illustrative images. Cards export as `.apkg` or `.csv`.

**Tech Stack:**
- Python 3.12+
- Gradio 6 (frontend UI)
- llama.cpp runtime (via `InferenceEngine` protocol)
- TildeOpen (translation model, CEFR-aware text generation)
- OmniVoice (text-to-speech)
- FLUX.2-klein-4B (image generation)
- uv (dependency management), Hugging Face Hub (model weights)

**Architecture at a glance:**
- `core/` — types, inference engine, batch pipeline
- `frontend/` — Gradio UI: widgets, card rendering, custom CSS
- `models/` — HF Hub model downloader
- `export/` — .apkg generator, CSV export, Anki tunnel sync
- `app.py` — entry point, wires everything together

## Code Structure

### Module Boundaries

| Module | Do | Don't |
|---|---|---|
| `core/` | Define types, implement inference protocols, orchestrate batch pipelines | Import from `frontend/` or `export/` |
| `frontend/` | Render UI, handle Gradio events, style cards | Implement inference logic or export formats |
| `models/` | Download and locate models | Run inference or generate content |
| `export/` | Generate .apkg, .csv, communicate with Anki tunnel | Import from `frontend/` |
| `app.py` | Wire modules together, define Gradio click handlers | Contain business logic (delegate to `core/`) |

### File Organization Rules

1. **One responsibility per file.** `cards.py` renders cards. `widgets.py` creates form controls. `pipeline.py` orchestrates batching. Don't mix responsibilities.
2. **`__init__.py` files are minimal.** Just package markers — no imports, no logic.
3. **UI components live in `frontend/ui/`.** Not in `app.py`. If a widget or renderer grows beyond ~100 lines, consider whether it needs its own file.
4. **CSS lives in `frontend/css/custom.css`.** Inline styles are acceptable in card HTML (for portability when rendered as strings), but theme-level rules go in the CSS file.
5. **Config lives in `configs/settings.yaml`.** Hard-coded values belong here, not scattered across modules.

### Import Conventions

- Use absolute imports from project root: `from core.types import CardData`
- Import Gradio as `import gradio as gr` (not `from gradio import ...`)
- Never import from `frontend/` in `core/`, `models/`, or `export/` — the frontend depends on everything, not vice versa

```

- [ ] **Step 1: Write AGENTS.md with Project Overview and Code Structure sections**

Create `/home/takosaga/Projects/EuropaLex/AGENTS.md` with the content above.

- [ ] **Step 2: Verify file exists and is valid markdown**

```bash
head -60 /home/takosaga/Projects/EuropaLex/AGENTS.md
```

Check that:
- File starts with `# EuropaLex — AI Agent Conventions`
- Project Overview section lists all tech stack items
- Code Structure table accurately reflects module boundaries
- Import conventions match actual code patterns (e.g., `import gradio as gr`)

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add AGENTS.md
git commit -m "docs: add AGENTS.md — AI agent conventions (overview + structure)"
```

---

### Task 5: Create AGENTS.md — Code Conventions and Frontend Patterns

**Files:**
- Modify: `AGENTS.md` — append sections after Code Structure

Append the following sections to `AGENTS.md`:

```markdown
## Code Conventions

### Naming

- **Modules (lowercase, underscore):** `apkg_generator`, `anki_tunnel`, `download_models`
- **Classes (PascalCase):** `InferenceEngine`, `CardData`, `CEFRLevel`, `LocalInference`
- **Functions/variables (snake_case):** `render_card_html`, `generate_cards_html`, `batch_size`
- **Constants (UPPER_SNAKE_CASE):** None currently needed; keep config in YAML

### Style

- Type hints on all public functions. Private/helper functions may omit if trivially obvious.
- Docstrings: one-line summary + args/returns for multi-arg functions. See `frontend/ui/widgets.py:create_toggle()` as the template.
- No trailing whitespace. 4-space indentation (standard Python).
- Max line length: 100 characters. Break function calls and long strings.

### Data Flow Through the App

```
User input → app.py click handler → core/engine.py inference → core/pipeline.py batching → frontend/ui/cards.py rendering → Gradio output
```

When adding a new feature, follow this chain. Don't bypass `pipeline.py` — even single-card generation should go through it for consistency.

## Frontend Patterns

### Gradio Widget Creation

Use the wrapper functions in `frontend/ui/widgets.py`. Example:

```python
from frontend.ui.widgets import create_toggle

images_toggle = create_toggle("🖼️ Images", value=True, elem_id="toggle-images")
audio_toggle = create_toggle("🔊 Audio", value=False, elem_id="toggle-audio")
```

The `elem_id` follows the pattern: `toggle-<label-without-emoji>`. This is used for CSS targeting and two-phase disabled state management.

### Card Rendering

All card HTML goes through `frontend/ui/cards.py`:

- `render_card_html(card_data, include_image, include_audio, rotation, placeholder_back)` — single card
- `generate_cards_html(cards, include_image, include_audio, placeholder_back)` — full gallery

**Rules:**
- Never construct card HTML inline in `app.py`. Always call these functions.
- The `rotation` parameter creates the "spread on desk" visual effect. Use the rotation distribution logic from `generate_cards_html()` — don't hard-code angles.
- `placeholder_back=True` shows a dashed placeholder line instead of translation text (used during Phase 1 before translations are generated).

### Two-Phase Generation Workflow

The UI operates in two distinct phases:

**Phase 1 — Generate Text:**
1. User clicks "Generate Text"
2. `app.py` calls the text generation handler → TildeOpen produces English + translation
3. Cards render with text but media toggles are disabled (CSS opacity + pointer-events)
4. After completion, `_enable_phase2()` removes disabled CSS and enables toggles + "Generate Cards" button

**Phase 2 — Generate Media:**
1. User toggles Images/Audio on/off
2. User clicks "Generate Cards"
3. `app.py` calls the media generation handler → OmniVoice (TTS) + FLUX.2 (images) fill in media
4. Both buttons hide during generation, reappear when done

**Rules:**
- Never skip Phase 1. Even if media-only mode seems useful, text must be generated first.
- When user changes input parameters (scenario, CEFR level, batch size), call `_reset_to_idle()` to restore disabled states and hidden buttons.
- The disabled state uses CSS class `europalex-btn-disabled` and inline styles with `#phase-css` ID. Don't remove these — they're tied to the two-phase state machine.

### Progress Tracking

Use `frontend/ui/cards.py:generate_progress_html(percent, phase_label)`. The function handles:
- Color transitions (brown → dark brown at 100%)
- Width animation via inline CSS
- Phase label text ("Generating text..." vs "Generating media...")

Return empty string (`""`) when `percent <= 0` — Gradio will hide the element.

```

- [ ] **Step 1: Append Code Conventions and Frontend Patterns sections to AGENTS.md**

Read the current `AGENTS.md`, find the end of the Code Structure section, and append the two new sections exactly as shown above.

- [ ] **Step 2: Verify AGENTS.md is complete**

```bash
wc -l /home/takosaga/Projects/EuropaLex/AGENTS.md && tail -30 /home/takosaga/Projects/EuropaLex/AGENTS.md
```

Check that:
- File has all sections in order: Project Overview → Code Structure → Code Conventions → Frontend Patterns
- Two-phase workflow is documented with the correct handler names (`_enable_phase2`, `_reset_to_idle`)
- Card rendering rules reference the actual function signatures from `cards.py`

- [ ] **Step 3: Commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add AGENTS.md
git commit -m "docs: add AGENTS.md — code conventions and frontend patterns"
```

---

### Task 6: Create AGENTS.md — Core Module Rules, Testing, Adding Features, Git Workflow, Known Pitfalls

**Files:**
- Modify: `AGENTS.md` — append final sections

Append the following sections to `AGENTS.md`:

```markdown
## Core Module Rules

### types.py

The canonical data shapes. If you add a new field to `CardData` or `CEFRLevel`, update it here first and propagate changes everywhere that consumes these types.

```python
# Template — match this structure:
@dataclass
class CardData:
    text: str              # English source text
    translation: str       # Target-language translation (empty during Phase 1)
    audio_path: str | None = None   # Path to generated TTS audio
    image_path: str | None = None   # Path to generated illustration
```

### engine.py

The `InferenceEngine` protocol defines the interface. Implementations wrap different backends (local llama.cpp vs Modal-hosted). **Rules:**
- Never bypass the protocol — all inference goes through `InferenceEngine.generate()` or equivalent.
- Each implementation should be self-contained. Don't share state between `LocalInference` and `ModalInference`.

### pipeline.py

The batch orchestrator. It receives a list of texts and produces batches of (text, audio, image) outputs based on toggle state. **Rules:**
- Pipeline is the single point of parallelism control. If adding new media types, add them here first.
- Use generator functions (`yield`) for streaming progress updates — Gradio consumes generators for real-time UI updates.

## Testing Expectations

### Smoke Tests

Run `scripts/smoke_test.py` before committing. It performs a quick sanity check: imports all modules, validates dataclasses, and checks that the Gradio app can be constructed without errors.

```bash
python scripts/smoke_test.py
```

Expected output: clean exit (no traceback). If it fails, something is broken at the module level.

### Mock Data

The frontend can render cards from mock data (no model inference needed). When testing UI changes:
- Use `frontend/ui/cards.py:render_card_html()` directly with a dict like `{"text": "Hello", "translation": "Sveiki"}`
- The card renderer handles missing fields gracefully — `translation` defaults to empty string, `audio_path`/`image_path` are ignored in HTML rendering.

### No Unit Test Framework Required (Yet)

The project currently uses smoke tests only. If you add a new module with non-trivial logic (>30 lines of business logic), consider adding inline assertions or a simple test function at the bottom of the file guarded by `if __name__ == "__main__":`.

## Adding New Features

Use this checklist when extending EuropaLex:

1. **Identify the module** — Where does the feature belong? (See Code Structure table.)
2. **Define types first** — If the feature introduces new data, add it to `core/types.py`.
3. **Implement core logic** — In `core/` or the appropriate module. Follow the protocol pattern from `engine.py`.
4. **Wire up the UI** — Add widgets in `frontend/ui/widgets.py`, renderers in `frontend/ui/cards.py`. Update `app.py` click handlers last.
5. **Update CSS if needed** — New visual elements go in `frontend/css/custom.css`. Keep inline styles only for card-level dynamic properties (rotation, conditional display).
6. **Test with smoke test** — Run `python scripts/smoke_test.py`.
7. **Commit** — One logical change per commit. Message format: `type: brief description` (e.g., `feat: add Japanese language support`, `fix: card rotation overflow`).

## Git Workflow

### Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/) prefix:
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `style:` — formatting, no code change
- `refactor:` — code restructuring, no behavior change
- `test:` — test-related changes

### Branch Strategy

- Work on feature branches: `feat/<feature-name>` (e.g., `feat/gradio_frontend`, `feat/japanese-support`)
- Keep main clean — only merge when a feature is complete and tested.
- Commit frequently within branches (every 2-5 minutes of work).

### Before Merging

1. Run `python scripts/smoke_test.py` — must pass
2. Verify the Gradio app starts: `python app.py` — must launch without errors on port 7860
3. Check that all new code follows the conventions in this document

## Known Pitfalls

### 1. Don't inline card HTML in app.py

Card rendering belongs in `frontend/ui/cards.py`. If you find yourself building `<div>` strings in `app.py`, move them to a function in `cards.py` or `widgets.py`.

### 2. Two-phase state machine is fragile

The disabled/enabled toggle states are managed via CSS injection (`#phase-css`) and Gradio element re-rendering. If you add new phase-dependent controls, remember to:
- Give them an `elem_id` for targeting
- Include them in `_reset_to_idle()` outputs
- Include them in `_enable_phase2()` outputs

### 3. Gradio generator functions must yield tuples

When a click handler produces multiple outputs (e.g., progress bar + card gallery), it must be a generator that yields tuples matching the output order:

```python
def my_handler(...):
    # ... work ...
    yield progress_html, cards_html
```

If you forget `yield`, Gradio will not update the UI.

### 4. CSS specificity wars with Gradio

Gradio's default styles use `!important` heavily. Our `custom.css` also uses `!important` to override them. If a style isn't taking effect:
- Check if Gradio re-renders the element (re-rendered elements may get new inline styles)
- Increase specificity or add another `!important`
- Use `elem_id` targeting instead of class selectors when possible

### 5. Model paths are runtime-resolved

Models live in a configurable directory (default: `./models/`). Never hard-code model file paths. Always use the paths returned by `models/download_models.py` or read from `configs/settings.yaml`.

```

- [ ] **Step 1: Append final sections to AGENTS.md**

Read the current `AGENTS.md`, find the end of the Frontend Patterns section, and append all five new sections (Core Module Rules through Known Pitfalls) exactly as shown above.

- [ ] **Step 2: Verify AGENTS.md is complete and consistent**

```bash
wc -l /home/takosaga/Projects/EuropaLex/AGENTS.md && grep "^## " /home/takosaga/Projects/EuropaLex/AGENTS.md
```

Check that:
- All 9 sections are present in order
- No section headers are duplicated or missing
- File ends with the Known Pitfalls section (no trailing whitespace)

- [ ] **Step 3: Final commit**

```bash
cd /home/takosaga/Projects/EuropaLex
git add AGENTS.md
git commit -m "docs: add AGENTS.md — core rules, testing, feature checklist, git workflow, pitfalls"
```

---

### Task 7: Final Verification and Sync

**Files:**
- Verify: `README.md`, `AGENTS.md`

- [ ] **Step 1: Full README verification**

```bash
grep "^## " /home/takosaga/Projects/EuropaLex/README.md
```

Expected section order:
1. Hackathon Criteria
2. Setup
3. Repository Structure
4. CEFR Levels
5. Workflow (NEW)
6. Architecture (NEW)

- [ ] **Step 2: Full AGENTS.md verification**

```bash
grep "^## \|^### " /home/takosaga/Projects/EuropaLex/AGENTS.md
```

Expected section order:
1. Project Overview
2. Code Structure
3. Code Conventions
4. Frontend Patterns
5. Core Module Rules
6. Testing Expectations
7. Adding New Features
8. Git Workflow
9. Known Pitfalls

- [ ] **Step 3: Smoke test**

```bash
cd /home/takosaga/Projects/EuropaLex && python scripts/smoke_test.py
```

Expected: clean exit with no errors.

- [ ] **Step 4: Final commit of any changes from verification**

If steps 1-3 reveal issues, fix them and commit. If everything passes:

```bash
cd /home/takosaga/Projects/EuropaLex
git log --oneline -5
```

Verify the last 3 commits are our documentation additions.

```
