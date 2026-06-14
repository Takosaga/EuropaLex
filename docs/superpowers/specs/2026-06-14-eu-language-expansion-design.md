# EuropaLex — EU Language Expansion Design

**Date:** 2026-06-14
**Status:** Approved

## Goal

Expand EuropaLex's target language support from **8 to 23 languages** by adding all official European Union member-state languages that are supported by the tiny-aya translation model.

## Background

EuropaLex currently supports 8 EU languages: Latvian, Spanish, French, German, Polish, Italian, Portuguese, Finnish. The tiny-aya-water translation model (used in Phase 2) was trained on 70+ languages including all official EU languages. This change adds the remaining 15 official EU languages that tiny-aya supports.

## Scope

### In Scope

- Add 15 new official EU languages to the target language dropdown
- Update ISO 639-1 abbreviation mapping for export filenames
- Update documentation (README.md, AGENTS.md) to reflect the expanded language list
- Tests auto-adapt via dynamic iteration over `_LANGUAGE_ABBREVS` keys

### Out of Scope

- Adding non-EU languages (Welsh, Ukrainian, Arabic, Chinese, etc.) that tiny-aya supports
- UI redesign — scrollable dropdown remains unchanged in layout
- Model changes or new translation models
- Backend pipeline changes — all 23 languages use the same `LlamaCppTextEngine`

## Language List

### Existing Languages (8)

Latvian, Spanish, French, German, Polish, Italian, Portuguese, Finnish

### New Languages (15)

Bulgarian, Croatian, Czech, Danish, Dutch, Estonian, Greek, Hungarian, Lithuanian, Maltese, Romanian, Slovak, Slovenian, Swedish, Irish

**Total: 23 languages** (alphabetically ordered in the dropdown)

> **Note:** Welsh is excluded — it is a regional/minority language, not an official EU member-state language, and the UK has left the EU.

## ISO 639-1 Abbreviation Mapping

| Language | Code | EU Accession Year |
|---|---|---|
| Bulgarian | BG | 2007 |
| Croatian | HR | 2013 |
| Czech | CS | 2004 |
| Danish | DA | 1973 |
| Dutch | NL | 1958 |
| Estonian | ET | 2004 |
| Greek | EL | 1981 |
| Hungarian | HU | 2004 |
| Irish | GA | 2007 |
| Lithuanian | LT | 2004 |
| Maltese | MT | 2004 |
| Romanian | RO | 2007 |
| Slovak | SK | 2004 |
| Slovenian | SL | 2004 |
| Swedish | SV | 1995 |

## Files to Change

### 1. `export/csv_export.py`

Add 15 new entries to the `_LANGUAGE_ABBREVS` dictionary (lines ~10-18):

```python
_LANGUAGE_ABBREVS: dict[str, str] = {
    "Bulgarian": "BG",
    "Croatian": "HR",
    # ... 13 more new entries ...
    # Existing 8 entries remain unchanged
}
```

### 2. `frontend/ui/widgets.py`

Update the `language_dropdown` choices list (line ~290) from:

```python
choices=["Latvian", "Spanish", "French", "German", "Polish", "Italian", "Portuguese", "Finnish"],
```

to:

```python
choices=["Bulgarian", "Croatian", "Czech", "Danish", "Dutch", "Estonian", "Finnish", "French",
         "German", "Greek", "Hungarian", "Irish", "Italian", "Latvian", "Lithuanian", "Maltese",
         "Polish", "Portuguese", "Romanian", "Slovak", "Slovenian", "Spanish", "Swedish"],
```

Default remains `"Latvian"`.

### 3. `README.md`

Update the Phase 2 language list in the documentation to reflect all 23 languages. The subtitle ("AI-powered flashcard generator — translate text into European languages") is already accurate and does not need changing.

### 4. `AGENTS.md`

Update any hardcoded references to "8 supported languages" or the inline language list (e.g., in the Phase 2 workflow description).

## Test Impact

`tests/csv_export_test.py:test_all_languages_mapped()` iterates over `_LANGUAGE_ABBREVS.keys()` dynamically, so it will automatically cover all 23 languages without modification. The `test_all_languages_work()` fixture test also uses a dynamic language list and will auto-extend.

No new tests are needed.

## Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Dropdown too long for mobile UI | Low | Gradio's native dropdown scrolls; tested with similar-length lists |
| New language codes incorrect | Very low | ISO 639-1 codes are standardized and verified |
| tiny-aya poor quality on new languages | Low | Model was trained on these languages; quality varies but is acceptable for flashcard use |
| Documentation inconsistencies | Medium | Update all hardcoded references in a single pass |

## Success Criteria

1. All 23 official EU languages appear in the target language dropdown (alphabetically ordered)
2. Export filenames use correct ISO 639-1 codes for all 23 languages
3. `uv run pytest tests/ -v` passes with no modifications to test files
4. README.md and AGENTS.md reflect the expanded language list
