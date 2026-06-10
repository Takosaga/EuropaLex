# Split Translation Out of Phase 1 — Design

## Problem

Phase 1 currently generates both English text (Nemotron) and translation (tiny-aya-water). Translation is a GPU-heavy operation (~2 GB VRAM) that adds unnecessary latency before the user even sees the English text. The user's intent is to see English first, then decide whether to generate translations and media in Phase 2.

## Solution

Remove translation from Phase 1 entirely. Phase 1 generates only English text. Translation runs alongside TTS and images in Phase 2.

## Changes

### app.py — Phase 1 handler

**Before:** Calls Nemotron for English text, then calls `LlamaCppTextEngine` (tiny-aya-water) for translation. Both engines load sequentially in Phase 1.

**After:** Calls only Nemotron (`TextEngine`, subprocess-based, no persistent VRAM). No translation step. Cards render with English on front, dashed placeholder back.

### app.py — Phase 2 handler (deferred)

**Out of scope for this cycle.** Will be implemented separately: add `LlamaCppTextEngine` call for translation at the start of Phase 2, then TTS + images. Translation appears on card front alongside media; English moves to back.

### core/pipeline.py — Batch orchestration

**Phase 1 batch:** Only text outputs (English). No translation step.

**Phase 2 batch (deferred):** Translation → audio → image outputs. Will be updated in a follow-up.

### EnginePool lifecycle

**Before Phase 1:** No engines loaded.
**During Phase 1:** `TextEngine` only (subprocess, no VRAM).
**After Phase 1:** `TextEngine` unloaded (no state to preserve).
**During Phase 2:** `LlamaCppTextEngine` loads for translation (~2 GB), unloads after; then `TTSEngine` or `ImageGenEngine` loads as needed.

**Before Phase 2:** Both Nemotron and tiny-aya-water were loaded sequentially.

### AGENTS.md — Documentation

Update the "Two-Phase Generation Workflow" section to reflect:
- Phase 1: Generate English text (Nemotron only)
- Phase 2: Generate Translation + Media (deferred — tiny-aya-water → TTS → images)

Also update the data flow diagram and engine descriptions where they reference Phase 1 loading GPU engines.

## What Does Not Change

- Card layout and rendering logic (unchanged)
- Media generation (TTS + images work the same)
- Toggles, progress tracking, disabled/enabled state management
- EnginePool mutual exclusion logic
- All other module boundaries and conventions

## Files Modified

| File | Change |
|---|---|
| `app.py` | Remove translation call from Phase 1 handler |
| `core/pipeline.py` | Update batch config for Phase 1 (text-only); Phase 2 batch updated in follow-up |
| `AGENTS.md` | Update two-phase workflow section, data flow diagram, engine lifecycle notes |

## Out of Scope

Phase 2 handler changes (adding translation call) are deferred to a separate cycle. Only Phase 1 is in scope for this implementation.

## Risk Assessment

- **Low risk.** Translation is a simple function call — adding it to Phase 2 and removing from Phase 1 is a localized change.
- **No new dependencies or interfaces.** Same engines, different call sites.
- **User-visible improvement:** Phase 1 completes faster (no ~2 GB GPU load + translation time). User sees English text sooner.
