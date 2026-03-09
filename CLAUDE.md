# LocalTax — Claude Code Project Briefing

> **Full PRD is in `/PRD.md` — reference it with `@PRD.md` for complete specifications.**
> Always read `@PRD.md` before starting any new feature or pipeline step.

---

## What This Project Is

LocalTax is a fully local, private tax preparation assistant that processes IRS source
documents and populates IRS tax forms — no cloud, no TurboTax, no sensitive data leaving
the machine. Everything runs locally on Windows using Python, Streamlit, and Ollama.

---

## Stack

- **UI:** Streamlit (local browser at localhost:8501)
- **OCR:** pdfplumber (digital PDFs) + pytesseract (scanned docs) + pdf2image
- **LLM Runtime:** Ollama (local, CPU-only, 16GB RAM, no GPU)
- **PDF Form Filling:** pypdf (AcroForm fields)
- **Data:** Flat JSON files — no database
- **Language:** Python 3.11+
- **OS:** Windows

---

## The 5-Step Pipeline

| Step | Name | Model | Input → Output |
|------|------|-------|----------------|
| 1 | OCR Extractor | None (Python) | Raw PDFs → .txt files |
| 2 | LLM Formatter | llama3.1:8b | .txt files → structured JSON |
| 3 | Mapping Builder | deepseek-r1:7b | Prior year return → field mapping JSON |
| 4 | Form Populator | llama3.1:8b | JSON + mapping → populated form values JSON |
| 5 | PDF Filler | None (pypdf) | Populated JSON → filled IRS PDF forms |

Each step is manually triggered in the UI. No step auto-proceeds without user approval.

---

## Folder Structure

```
/taxProject
  /2024
    /input        ← source PDFs (W-2, 1099s, etc.)
    /extracted    ← OCR output (.txt per document)
    /mapped
      /formatted  ← Step 2 JSON output
      /populated  ← Step 4 JSON output
    /output       ← final filled IRS PDF forms
    /logs         ← full session logs (timestamped JSON)
    /ground_truth ← filed 2024 return (validation reference)
  /2025           ← same structure, populated next cycle
  /templates      ← blank IRS fillable PDFs (downloaded once)
  /prompts
    /schemas      ← JSON schema templates per document type
  app.py          ← Streamlit entry point
  config.json     ← model names, paths, thresholds
  requirements.txt
```

---

## Source Documents (2024)

W-2, 1095-C, 1099-INT, 3922 (ESPP), 1099-DIV (x2), 5498 (IRA), 1099-SA (HSA), 1099-B

## Federal Forms to Populate

Form 1040, Schedule 1, Schedule 3, Schedule B, Schedule D, Form 8949, Form 8889

---

## Build Order (follow this strictly)

1. **M1** — Project scaffolding: folder structure, config.json, Streamlit shell
2. **M2** — Step 1 OCR: pdfplumber + pytesseract, auto-detect digital vs scanned
3. **M3** — Step 2 LLM Formatter: Ollama integration, JSON schemas, retry logic
4. **M4** — Step 5 PDF Filler: pypdf AcroForm field filling
5. **M5** — First end-to-end test: W-2 + 1099-INT → Schedule B → 1040
6. **M6** — Form 8889 (HSA): 1099-SA + 5498
7. **M7** — Schedule D + Form 8949 (ESPP — hardest step, needs cost basis adjustment)
8. **M8** — Step 3 Mapping Builder: ground truth extraction from 2024 filed return
9. **M9** — Full validation run against 2024 filed return
10. **M10** — Prior year comparison UI (flag >20% differences)
11. **M11** — Polish, logging, edge case handling

**Current milestone:** Start with M1.

---

## Human-in-the-Loop Checkpoints

User must explicitly approve output at every step before proceeding:
- After Step 1 (OCR text)
- After Step 2 (formatted JSON — fields are individually editable)
- After Step 3 (field mappings)
- After Step 4 (populated form values — last chance before PDF is written)

---

## Key Rules & Constraints

- **Never auto-proceed** between pipeline steps — always wait for user approval
- **LLM uncertainty:** if the model flags a value as uncertain, show a modal and block
  progression until user resolves it (confirm / correct / skip)
- **Malformed JSON:** auto-retry once with stricter prompt; if still fails, show raw
  output to user for manual repair
- **Corrupted PDF:** log error, skip file, show red warning — do not halt entire pipeline
- **Missing fields:** set to null, flag with yellow warning, prompt user to fill manually
- **All logs saved** to /2024/logs/ — every edit, every LLM call, every approval
- **No authentication** — local only (localhost), single user
- **Source PDFs kept as-is** (unencrypted) after processing
- **ESPP / Form 8949:** cost basis must be adjusted — ordinary income already on W-2,
  do NOT double-count. This is the highest-risk mapping step.

---

## Ollama Models

Both must be pulled before running:
```
ollama pull llama3.1:8b
ollama pull deepseek-r1:7b
```

Ollama must be running (system tray) before launching the app.

---

## Testing Strategy

- Use 2024 source docs as input
- Compare every output field against filed 2024 return (ground truth)
- Target: 100% match on all dollar-value fields before trusting on live 2025 filing
- This is a validation year — do NOT file live until fully verified

---

## What Is NOT in Scope (Phase 1)

- No California state taxes (Phase 2 — future)
- No e-filing (print and mail only for now)
- No multi-user support
- No cloud sync or external APIs

---

## Reference

For full specifications including error handling, UI layout, JSON schemas, step-by-step
Windows setup, and milestone details — always read:

```
@PRD.md
```