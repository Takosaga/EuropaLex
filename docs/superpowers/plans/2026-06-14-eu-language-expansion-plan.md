# EU Language Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand EuropaLex's target language support from 8 to 23 official EU languages by adding ISO 639-1 codes, updating the dropdown choices, and synchronizing documentation.

**Architecture:** Two data sources feed the feature: `export/csv_export.py:_LANGUAGE_ABBREVS` (ISO code mapping for export filenames) and `frontend/ui/widgets.py:language_dropdown.choices` (UI dropdown list). Both must be updated together. Documentation in README.md and AGENTS.md lists the current languages inline and must also be refreshed. The test suite already iterates over `_LANGUAGE_ABBREVS.keys()` dynamically, so no test code changes are needed.

**Tech Stack:** Python 3.12+, Gradio 6, pytest — no new dependencies.

---

### Task 1: Add new ISO 639-1 language codes to csv_export.py

**Files:**
- Modify: `export/csv_export.py:10-18`

- [ ] **Step 1: Update `_LANGUAGE_ABBREVS` dict with all 23 languages**

Replace the entire `_LANGUAGE_ABBREVS` dictionary (lines 10-18) with an alphabetically-sorted dict containing all 23 languages:

```python
# ISO 639-1 language abbreviation mapping
_LANGUAGE_ABBREVS: dict[str, str] = {
    "Bulgarian": "BG",
    "Croatian": "HR",
    "Czech": "CS",
    "Danish": "DA",
    "Dutch": "NL",
    "Estonian": "ET",
    "Finnish": "FI",
    "French": "FR",
    "German": "DE",
    "Greek": "EL",
    "Hungarian": "HU",
    "Irish": "GA",
    "Italian": "IT",
    "Latvian": "LV",
    "Lithuanian": "LT",
    "Maltese": "MT",
    "Polish": "PL",
    "Portuguese": "PT",
    "Romanian": "RO",
    "Slovak": "SK",
    "Slovenian": "SL",
    "Spanish": "ES",
    "Swedish": "SV",
}
```

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `uv run pytest tests/csv_export_test.py -v`

Expected: All tests pass (the dynamic `_LANGUAGE_ABBREVS` iteration in `test_all_languages_mapped` will now cover 23 languages instead of 8).

- [ ] **Step 3: Commit**

```bash
git add export/csv_export.py
git commit -m "feat: expand ISO 639-1 language mapping to 23 EU languages"
```

---

### Task 2: Update the language dropdown choices in widgets.py

**Files:**
- Modify: `frontend/ui/widgets.py:285-287` (the `language_dropdown` definition inside `build_ui()`)

- [ ] **Step 1: Replace the hardcoded choices list with all 23 languages**

Find the `language_dropdown` definition in `build_ui()` (approximately line 285) which currently reads:

```python
choices=["Latvian", "Spanish", "French", "German", "Polish", "Italian", "Portuguese", "Finnish"],
```

Replace with alphabetically sorted choices:

```python
choices=[
    "Bulgarian", "Croatian", "Czech", "Danish", "Dutch", "Estonian",
    "Finnish", "French", "German", "Greek", "Hungarian", "Irish",
    "Italian", "Latvian", "Lithuanian", "Maltese", "Polish",
    "Portuguese", "Romanian", "Slovak", "Slovenian", "Spanish", "Swedish",
],
```

Keep `value="Latvian"` unchanged.

- [ ] **Step 2: Run smoke tests to verify app construction**

Run: `uv run pytest tests/smoke_test.py -v`

Expected: All imports succeed, Gradio Blocks constructs without errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/ui/widgets.py
git commit -m "feat: expand language dropdown to 23 EU languages"
```

---

### Task 3: Update README.md language list

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Phase 2 language list**

Find the Phase 2 workflow section that lists supported languages. It reads:

```markdown
1. Select a target language from the **Target Language** dropdown (Latvian, Spanish, French, German, Polish, Italian, Portuguese, Finnish)
```

Replace with:

```markdown
1. Select a target language from the **Target Language** dropdown (23 EU languages: Bulgarian, Croatian, Czech, Danish, Dutch, Estonian, Finnish, French, German, Greek, Hungarian, Irish, Italian, Latvian, Lithuanian, Maltese, Polish, Portuguese, Romanian, Slovak, Slovenian, Spanish, Swedish)
```

- [ ] **Step 2: Update the architecture/data-flow section**

Find any inline language lists in the Architecture or Workflow sections and update them. Specifically, search for "Latvian, Spanish" patterns and replace with the full list or a reference like "(23 EU languages)".

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update language list to 23 EU languages in README"
```

---

### Task 4: Update AGENTS.md language references

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Update the Phase 2 workflow description**

Find the inline language list in the Phase 2 workflow section (around the "Select a target language" bullet) and replace with:

```markdown
1. Select a target language from the **Target Language** dropdown (23 EU languages)
```

Or expand to full alphabetical list if the original was detailed.

- [ ] **Step 2: Update any hardcoded "8 supported languages" references**

Search for patterns like "8 supported", "Latvian, Spanish" inline lists and update them to reflect 23 languages.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update language list to 23 EU languages in AGENTS.md"
```

---

### Task 5: Final verification

**Files:**
- All modified files from Tasks 1-4

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`

Expected: All tests pass, including the new language coverage in `csv_export_test.py`.

- [ ] **Step 2: Verify app construction**

Run: `uv run pytest tests/smoke_test.py -v`

Expected: App constructs without errors.

- [ ] **Step 3: Final commit (if not already committed per task)**

```bash
git add -A
git commit -m "feat: expand to all 23 official EU languages supported by tiny-aya"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Add 15 new ISO 639-1 codes → Task 1
- ✅ Update dropdown choices → Task 2
- ✅ Update README.md → Task 3
- ✅ Update AGENTS.md → Task 4
- ✅ Tests auto-adapt → verified in Task 1 (no code changes needed)

**2. Placeholder scan:** No "TBD", "TODO", or vague instructions found. All steps contain exact file paths, line references, and complete code.

**3. Type consistency:** All language names use Title Case throughout. ISO codes are uppercase two-letter codes. No type mismatches.

**4. Scope check:** Focused — only adds languages, no new features, no model changes, no pipeline changes. Single implementation plan.
