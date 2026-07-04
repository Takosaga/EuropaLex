# HF Spaces Deployment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ZeroGPU deployment support to EuropaLex so it runs on Hugging Face Spaces with all 4 models, while keeping local `uv` development unchanged.

**Architecture:** A conditional `@spaces.GPU` decorator pattern in `app.py` — detected via `try/except ImportError`, no-op locally, active on HF. Pre-compiled wheels in `requirements.txt` skip on-builder compilation. YAML frontmatter in README configures HF Spaces deployment metadata.

**Tech Stack:** Python 3.12+, Gradio 6, Hugging Face `spaces` SDK, pre-compiled torch/llama-cpp-python wheels, GGUF models via llama-cpp-python and diffusers.

## Global Constraints

- Local behavior must not change — `uv run app.py` works identically after changes
- All existing tests must pass after changes (`uv run pytest tests/smoke_test.py -v`)
- Pre-compiled wheel indices: torch from `https://download.pytorch.org/whl/cu128`, llama-cpp-python from `https://abetlen.github.io/llama-cpp-python/whl/cu124`
- GPU duration: 120 seconds per `@spaces.GPU` call
- Python version on HF Spaces: 3.13 (per YAML frontmatter)

---

### Task 1: Add conditional GPU decorator block to app.py

**Files:**
- Modify: `app.py` — add ~10 lines after existing imports, before `_auto_download_models()`

**Interfaces:**
- Produces: `gpu(fn)` decorator function and `_HF_SPACES` boolean flag used by later tasks

**Steps:**

- [ ] **Step 1: Add the conditional GPU decorator block**

Insert this block right after the existing import section (after the Gradio file response patch block, before `_auto_download_models()`):

```python
# ─── ZeroGPU support for HF Spaces ──────────────────────
try:
    import spaces
    _HF_SPACES = True
    def gpu(fn): return spaces.GPU(duration=120)(fn)
except ImportError:
    _HF_SPACES = False
    def gpu(fn): return fn  # no-op locally
```

- [ ] **Step 2: Run smoke test to verify local behavior unchanged**

Run: `uv run pytest tests/smoke_test.py -v`
Expected: All tests pass (no regression in imports or app construction)

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add conditional @spaces.GPU decorator for ZeroGPU"
```

---

### Task 2: Decorate inference entry points with @gpu

**Files:**
- Modify: `app.py` — add `@gpu` decorator to 4 functions/calls

**Interfaces:**
- Consumes: `gpu` decorator from Task 1
- Applies to: `generate_text_async`, translation call, TTS call, image gen call inside `generate_media_async`

**Steps:**

- [ ] **Step 1: Decorate `generate_text_async`**

Find the function definition:
```python
def generate_text_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
):
```

Add `@gpu` decorator above it:
```python
@gpu
def generate_text_async(
    scenario: str,
    cefr_level: str,
    batch_size: int,
):
```

- [ ] **Step 2: Decorate the translation call inside `generate_media_async`**

Find where the translation engine is called:
```python
translation = translation_engine._translate_single(
    english_text, cefr,
    topic_description=scenario,
    target_language=target_language,
)
```

Wrap it with a GPU-decorated helper. The cleanest approach: create a small inner function that wraps the call:

```python
@gpu
def _translate_single(engine, text, cefr, scenario, lang):
    return engine._translate_single(text, cefr, topic_description=scenario, target_language=lang)
```

Then replace the direct call:
```python
translation = _translate_single(
    translation_engine, english_text, cefr, scenario, target_language
)
```

- [ ] **Step 3: Decorate the TTS call inside `generate_media_async`**

Find the TTS block (after the translation loop):
```python
try:
    from core.audio_gen import TTSEngine
    tts_engine = pool.get_tts_engine()
    output_dir = Path(config.models_dir) / "output" / "audio"
    translations_list = [c["translation"] for c in cards]
    audio_result = tts_engine.synthesize(translations_list, output_dir, language=target_language, instruct=voice)
```

Wrap with a GPU-decorated helper:
```python
@gpu
def _synthesize(engine, texts, output_dir, language, instruct):
    return engine.synthesize(texts, output_dir, language=language, instruct=instruct)
```

Replace the direct call:
```python
audio_result = _synthesize(
    tts_engine, translations_list, output_dir, target_language, voice
)
```

- [ ] **Step 4: Decorate the image gen call inside `generate_media_async`**

Find the image generation block (after TTS):
```python
try:
    from core.image_gen import ImageGenEngine
    img_engine = pool.get_image_engine()
    output_dir = Path(config.models_dir) / "output" / "images"
    prompts = [...]
    image_result = img_engine.generate(prompts, output_dir)
```

Wrap with a GPU-decorated helper:
```python
@gpu
def _generate_images(engine, prompts, output_dir):
    return engine.generate(prompts, output_dir)
```

Replace the direct call:
```python
image_result = _generate_images(img_engine, prompts, output_dir)
```

- [ ] **Step 5: Run smoke test to verify no regressions**

Run: `uv run pytest tests/smoke_test.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: apply @spaces.GPU decorators to all inference entry points"
```

---

### Task 3: Update requirements.txt with pre-compiled wheels

**Files:**
- Modify: `requirements.txt` — replace entire file content

**Interfaces:**
- No code dependencies — this is a deployment config change only

**Steps:**

- [ ] **Step 1: Replace requirements.txt content**

Write the following to `requirements.txt`:

```
--extra-index-url https://download.pytorch.org/whl/cu128
--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

spaces
torch==2.8.0
hf_transfer
llama-cpp-python==0.3.29
gradio>=6.0.0
pydantic>=2.0.0
genanki>=0.13.0
huggingface-hub>=1.18.0
pyyaml>=6.0
soundfile>=0.12.0
omnivoice>=0.1.0
diffusers>=0.28.0
```

- [ ] **Step 2: Verify pyproject.toml is unchanged**

Ensure `pyproject.toml` still has all the same dependencies (it's used for local `uv sync`, not affected by this change).

Run: `grep -c "diffusers\|omnivoice\|soundfile\|genanki" pyproject.toml`
Expected: All packages still listed

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: update requirements.txt with pre-compiled wheels for ZeroGPU"
```

---

### Task 4: Add HF Spaces YAML frontmatter to README.md

**Files:**
- Modify: `README.md` — add YAML block at top

**Interfaces:**
- No code dependencies — documentation/deployment config change only

**Steps:**

- [ ] **Step 1: Add YAML frontmatter to top of README.md**

Insert this block at the very top of `README.md`, before the `# Europa Lex` heading:

```yaml
---
title: EuropaLex Flashcards
emoji: 🌍
colorFrom: purple
colorTo: yellow
sdk: gradio
sdk_version: 6.19.0
python_version: '3.13'
app_file: app.py
pinned: false
---
```

- [ ] **Step 2: Verify README renders correctly**

Run: `head -15 README.md`
Expected: YAML frontmatter block followed by `# Europa Lex` heading

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add HF Spaces YAML frontmatter to README"
```

---

### Task 5: Final verification

**Files:**
- No file changes — verification only

**Steps:**

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Verify app.py imports cleanly**

Run: `python -c "import ast; ast.parse(open('app.py').read()); print('OK')"`
Expected: `OK` (no syntax errors)

- [ ] **Step 3: Verify requirements.txt is valid pip format**

Run: `pip install --dry-run -r requirements.txt 2>&1 | tail -5`
Expected: No parse errors (may show "Would install" output — that's fine)

- [ ] **Step 4: Commit any remaining changes**

```bash
git add -A
git status
```

---

## Self-Review

**Spec coverage:**
- ✅ Conditional GPU decorator → Task 1
- ✅ Decorate 4 inference points (MiniCPM5, tiny-aya, OmniVoice, FLUX) → Task 2
- ✅ Pre-compiled wheels in requirements.txt → Task 3
- ✅ YAML frontmatter in README → Task 4
- ✅ Local behavior unchanged → smoke test in Tasks 1, 2, 5
- ✅ No .gitignore changes → excluded per user decision

**Placeholder scan:** All steps contain actual code, exact file paths, and specific commands. No "TBD", "TODO", or "similar to" references.

**Type consistency:** `gpu` decorator produced in Task 1 is consumed by Task 2 with the same signature. Helper functions (`_translate_single`, `_synthesize`, `_generate_images`) are defined inline within `generate_media_async` — no external interface conflicts.

---

Plan complete and saved to `docs/superpowers/plans/2026-07-04-hf-spaces-deployment.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
