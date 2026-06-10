# 2026-06-09 — README + AGENTS.md Design

## Topic

Document EuropaLex's user workflow and system architecture in the README, and create an AGENTS.md conventions guide for AI coding agents working on the repo.

## Decisions

### README: Enhance in place
- Keep all existing sections (intro, hackathon criteria, setup, model table, CEFR levels)
- Insert two new sections: **Workflow** (user-facing step-by-step) and **Architecture** (module overview + data flow)
- Update Repository Structure to match current file layout

### AGENTS.md: Full conventions doc
- Cover project overview, code structure, conventions, frontend patterns, core module rules, testing expectations, adding features checklist, git workflow, known pitfalls

## Approaches Considered

1. **Enhance README + full AGENTS.md** (recommended) — minimal disruption to existing docs, comprehensive agent guidance
2. **Rewrite README from scratch + minimal AGENTS.md** — discarded; loses useful existing content and is too light on agent guidance
3. **Hybrid README + pattern-reference AGENTS.md** — discarded; user preferred full conventions coverage

## Design Sections

### README New Sections

#### Workflow (user-facing)
1. Enter scenario/text, select CEFR level (A0–C2), set batch size
2. Click **Generate Text** → Phase 1: TildeOpen generates English text + target-language translations
3. Cards render with front/back text; media toggles shown but not yet active
4. Toggle Images and/or Audio on/off as desired
5. Click **Generate Cards** → Phase 2: OmniVoice generates TTS audio, FLUX.2 generates illustrative images
6. Export generated cards as `.apkg` (Anki package) or `.csv`

#### Architecture (developer-facing)
- **core/** — Data types (`types.py`), inference engine protocol + implementations (`engine.py`), batch pipeline orchestrator (`pipeline.py`)
- **frontend/** — Gradio 6 UI: `widgets.py` (styled toggles), `cards.py` (single card rendering, gallery layout, progress bar), `css/custom.css` (plain-white theme)
- **models/** — Hugging Face Hub model downloader script
- **export/** — `.apkg` generator, CSV export, Anki tunnel sync via MCP server
- **app.py** — Entry point; wires inputs to two-phase click handlers with progress tracking

### AGENTS.md Sections
1. Project Overview — what EuropaLex does, tech stack (Python, Gradio 6, llama.cpp, TildeOpen, OmniVoice, FLUX.2)
2. Code Structure — module boundaries and where to put new code
3. Code Conventions — naming, patterns, style rules
4. Frontend Patterns — Gradio widget creation, card rendering, two-phase workflow rules
5. Core Module Rules — engine protocol, pipeline batching, type usage
6. Testing Expectations — smoke tests, mock data approach
7. Adding New Features — step-by-step checklist
8. Git Workflow — commit conventions, branch strategy
9. Known Pitfalls — common mistakes to avoid

## Scope

Two deliverables: one updated README.md (in-place enhancement), one new AGENTS.md at repo root. No code changes.
