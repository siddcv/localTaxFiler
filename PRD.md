# LocalTax — Product Requirements Document
**Version:** 1.0  
**Date:** March 2026  
**Status:** Draft  
**Phase:** Phase 1 — Federal Only  
**Deadline:** April 15, 2026  

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tax Situation & Scope](#2-tax-situation--scope)
3. [System Architecture](#3-system-architecture)
4. [File & Folder Structure](#4-file--folder-structure)
5. [Web UI Specification](#5-web-ui-specification)
6. [Pipeline Step Specifications](#6-pipeline-step-specifications)
7. [Logging Specification](#7-logging-specification)
8. [Error Handling](#8-error-handling)
9. [Windows Setup Guide](#9-windows-setup-guide)
10. [Build Order & Milestones](#10-build-order--milestones)
11. [Testing Strategy](#11-testing-strategy)
12. [Security & Privacy](#12-security--privacy)
13. [Phase 2 — California (Placeholder)](#13-phase-2--california-state-taxes-placeholder)
14. [Open Questions](#14-open-questions--decisions-deferred)

---

## 1. Project Overview

LocalTax is a fully local, private tax preparation assistant that processes IRS source
documents and populates IRS tax forms — without paying for TurboTax or H&R Block, and
without uploading sensitive financial documents to any cloud service. All data stays on
the user's Windows machine.

The tool runs a 5-step pipeline: OCR extracts text from PDFs, two Ollama LLM passes
structure and map the data, a third LLM pass populates form fields, and a Python PDF
filler writes the final IRS forms. A local Streamlit web UI guides the user through each
step with manual review checkpoints at every stage.

> **Year One Goal:** Verify accuracy against the already-filed 2024 return before ever
> trusting this on a live 2025 filing. This is a test-and-validate year, not a
> fire-and-forget year.

### 1.1 Motivation

- Avoid ~$150–300 annual cost of commercial tax software
- Keep highly sensitive financial documents (SSN, income, brokerage data) off cloud servers
- Build a reusable, auditable pipeline that improves year over year
- Learn how a tax return is constructed from source documents

### 1.2 Non-Goals (Phase 1)

- No e-filing support — output PDFs are for print-and-mail or review only
- No California state tax forms (Phase 2 placeholder — see Section 13)
- No multi-user support — single user, single machine
- No cloud sync, no external APIs, no internet required after setup
- No automated filing — human must review and approve before submission

---

## 2. Tax Situation & Scope

### 2.1 Source Documents

| Document | Contents |
|----------|----------|
| W-2 | Wages and withholding from employer |
| 1095-C | Employer health coverage (ACA) |
| 1099-INT | Interest income from bank/brokerage |
| 3922 | ESPP stock transfer details |
| 1099-DIV (x2) | Dividend income — two issuers |
| 5498 | IRA contribution records |
| 1099-SA | HSA distributions |
| 1099-B | Brokerage sales — ESPP and other |

**Document format:** Mix of digital PDFs (downloaded from employer/brokerage portals)
and scanned paper documents. Both paths must be supported by the OCR layer.

### 2.2 Federal Forms Required

| Form | Purpose |
|------|---------|
| Form 1040 | Main individual income tax return |
| Schedule 1 | Additional income and adjustments |
| Schedule 3 | Additional credits and payments |
| Schedule B | Interest and dividend income detail |
| Schedule D | Capital gains and losses summary |
| Form 8949 | Individual sale/disposal transactions (ESPP) |
| Form 8889 | HSA contributions and distributions |

### 2.3 ESPP Complexity Note

Form 8949 / Schedule D entries for ESPP require special handling:

- The ordinary income component is already reported on the W-2 — double-counting must be avoided
- Cost basis must be adjusted to include the compensation element
- Wash sale rules may apply if shares were repurchased within 30 days
- Under 20 total transactions — manageable but each line requires careful mapping

> **This is the highest-risk step in the pipeline. Human review at this checkpoint is
> mandatory before proceeding to PDF population.**

---

## 3. System Architecture

### 3.1 The 5-Step Pipeline

The pipeline is linear and manual-trigger at each step. No step auto-proceeds to the
next without user approval.

| Step | Name | Description |
|------|------|-------------|
| Step 1 | OCR Extractor | pdfplumber + pytesseract → raw text |
| Step 2 | LLM Formatter | Ollama (llama3.1:8b) → clean structured JSON |
| Step 3 | Mapping Builder | Ollama (deepseek-r1:7b) → field mapping from prior year |
| Step 4 | Form Populator | Ollama (llama3.1:8b) → populated form values JSON |
| Step 5 | PDF Filler | pypdf (Python only) → completed IRS PDF forms |

### 3.2 Model Assignments Per Step

With 16GB RAM and no GPU, all models run on CPU via Ollama. Model selection is optimized
for CPU performance and JSON reliability:

| Step | Model | Rationale |
|------|-------|-----------|
| Step 2 — Formatter | llama3.1:8b | Most reliable for strict JSON schema output on CPU |
| Step 3 — Mapping Builder | deepseek-r1:7b | Better reasoning for cross-document field mapping |
| Step 4 — Populator | llama3.1:8b | Consistent JSON output for form field values |

> **Performance note:** On 16GB RAM CPU-only, expect 30–120 seconds per LLM call
> depending on prompt length. The pipeline is designed for accuracy and auditability,
> not speed.

### 3.3 Technology Stack

| Component | Technology |
|-----------|------------|
| Web UI Framework | Streamlit (Python) — local browser UI |
| OCR — Digital PDFs | pdfplumber — extracts text directly from true PDFs |
| OCR — Scanned Docs | pytesseract — OCR engine for image-based/scanned PDFs |
| PDF Detection | pdfplumber auto-detect: if text layer empty, fall back to tesseract |
| LLM Runtime | Ollama — local LLM server, runs on Windows CPU |
| PDF Form Filling | pypdf — reads and writes IRS AcroForm fields |
| Data Storage | Flat JSON files — no database required |
| Language | Python 3.11+ |
| Package Manager | pip (standard) |

---

## 4. File & Folder Structure

Recommended location: `C:\Users\YourName\Documents\LocalTax\`

```
localtax/
  2024/
    input/          ← source PDFs (W-2, 1099s, etc.)
    extracted/       ← OCR raw text output (.txt files per document)
    mapped/
      formatted/    ← Step 2 LLM JSON output
      populated/    ← Step 4 LLM JSON output
    output/         ← final filled IRS PDF forms
    logs/           ← full session logs (timestamped JSON)
    ground_truth/   ← filed 2024 return (used for validation)
  2025/
    input/
    extracted/
    mapped/
    output/
    logs/
  templates/        ← blank IRS fillable PDFs (downloaded once from IRS.gov)
  prompts/
    schemas/        ← JSON schema templates per document type (.txt files)
  app.py            ← main Streamlit application entry point
  config.json       ← user configuration (model names, paths, thresholds)
  requirements.txt  ← Python dependencies
```

---

## 5. Web UI Specification (Streamlit)

### 5.1 General UI Requirements

- Runs locally at `http://localhost:8501` — no authentication required
- System default color theme (Streamlit default)
- Single-user design — no login, no session management
- Persistent sidebar showing: current tax year, pipeline step status, active model
- Each pipeline step is a separate Streamlit page/tab

### 5.2 Pipeline Step Pages

Each step page follows the same layout pattern:

- **Header:** Step name, description, input/output summary
- **Action button:** "Run Step X" — triggers processing
- **Progress indicator:** spinner with status text during LLM/OCR processing
- **Review panel:** output displayed for human inspection before proceeding
- **Approve / Edit / Reject controls** at the bottom of each review panel
- **"Proceed to Step X+1" button** — only enabled after approval

### 5.3 Human Review Checkpoints

Review is mandatory at all four checkpoints. The UI blocks progression until the user
explicitly approves each step output:

| Checkpoint | What User Reviews |
|------------|------------------|
| After Step 1 — OCR | Raw extracted text shown per document. User can flag bad extractions before LLM sees them. |
| After Step 2 — JSON Formatting | Structured JSON displayed in editable fields. User can edit any individual field value before mapping. |
| After Step 3 — Field Mapping | Form field mappings shown in a table. User reviews each source value mapped to each IRS form field. |
| After Step 4 — PDF Population | Final populated values shown in a pre-flight table. Last chance to edit before PDF is written. |

### 5.4 Inline JSON Field Editing

At the Step 2 and Step 4 review screens, every extracted or populated field is
individually editable:

- Each field rendered as a labeled text input (`st.text_input`)
- Original LLM value shown as placeholder
- User can overwrite any field value before approving
- All edits are logged with a `manually_edited` flag in the session log
- A "Reset to LLM value" button per field allows reverting changes

### 5.5 LLM Uncertainty Handling

When the LLM flags a value as uncertain (low confidence, missing source data, or
conflicting signals):

- A yellow warning banner appears inline next to the field
- The field is pre-highlighted in the review UI
- A modal dialog prompts the user to confirm, correct, or skip the value
- The user must explicitly resolve every flagged field before approving the step
- Unresolved flags block the "Proceed" button

### 5.6 Prior Year Comparison

At the Step 4 review screen, a comparison panel shows:

- Side-by-side view: 2024 filed value vs. 2025 populated value per form field
- Fields with differences greater than 20% (configurable) are highlighted in orange
- User can click any flagged field to see the source documents that produced the new value
- Comparison is informational only — does not block approval

---

## 6. Pipeline Step Specifications

### Step 1: OCR Extraction

**Inputs:**
- Raw PDF files in `/2024/input/`
- One PDF per source document

**Processing Logic:**
- For each PDF: attempt pdfplumber text extraction
- If extracted text is empty or under 50 characters: fall back to pytesseract
- pytesseract path: convert PDF pages to images (pdf2image) then OCR each page
- Concatenate all page text into one `.txt` file per source document
- Named by document type: `w2.txt`, `1099_int.txt`, `1099_div_1.txt`, etc.

**Outputs:**
- One `.txt` file per source document saved to `/2024/extracted/`
- `extraction_summary.json`: filename, method used, page count, character count, warnings

**Error Handling:**
- Corrupted/unreadable PDF: log error, skip file, show red warning in UI — do not halt pipeline
- Zero-character output after both methods: flag as "extraction failed" — user must manually enter values
- Partial extraction (some pages failed): flag pages individually, continue with what was extracted

---

### Step 2: LLM Formatting (llama3.1:8b)

**Inputs:**
- Raw `.txt` files from `/2024/extracted/`
- Document type label (user selects from dropdown: W-2, 1099-INT, etc.)

**Processing Logic:**
- One Ollama API call per source document
- System prompt: output ONLY valid JSON, no preamble, no markdown fences
- User prompt: document type + raw OCR text + JSON schema template for that document type
- Each document type has its own schema template in `/prompts/schemas/`
- If LLM returns malformed JSON: auto-retry once with stricter prompt
- If second attempt also fails: log error, show raw output to user for manual JSON entry

**Outputs:**
- One `.json` file per source document saved to `/2024/mapped/formatted/`
- Examples: `w2_formatted.json`, `1099_int_formatted.json`

**JSON Schema — W-2 fields:**
```
employer_name, employer_ein, employee_ssn_last4, wages_box1,
federal_tax_withheld_box2, social_security_wages_box3,
social_security_tax_box4, medicare_wages_box5, medicare_tax_box6,
state, state_wages_box16, state_tax_box17
```

**JSON Schema — 1099-INT fields:**
```
payer_name, payer_ein, recipient_ssn_last4, interest_income_box1,
early_withdrawal_penalty_box2, us_savings_bond_interest_box3,
federal_tax_withheld_box4
```

**JSON Schema — 1099-DIV fields:**
```
payer_name, payer_ein, recipient_ssn_last4, total_ordinary_dividends_box1a,
qualified_dividends_box1b, total_capital_gain_box2a, federal_tax_withheld_box4
```

**JSON Schema — 1099-SA fields:**
```
trustee_name, trustee_ein, recipient_ssn_last4, gross_distribution_box1,
earnings_box2, distribution_code_box3, fair_market_value_box5
```

**JSON Schema — 5498 fields:**
```
trustee_name, trustee_ein, participant_ssn_last4, ira_contributions_box1,
rollover_contributions_box2, roth_ira_contributions_box10,
fair_market_value_box5
```

**JSON Schema — 3922 (ESPP) fields:**
```
company_name, company_ein, employee_ssn_last4, date_option_granted,
date_option_exercised, exercise_price_per_share, fmv_per_share_on_exercise_date,
shares_transferred, fmv_per_share_on_grant_date
```

**JSON Schema — 1099-B fields:**
```
payer_name, payer_ein, recipient_ssn_last4,
transactions: [
  { description, date_acquired, date_sold, proceeds, cost_basis,
    wash_sale_loss_disallowed, gain_loss, covered_uncovered, term }
]
```

---

### Step 3: Mapping Builder (deepseek-r1:7b)

**Inputs:**
- All formatted JSON files from `/2024/mapped/formatted/`
- User's filed 2024 return PDF in `/2024/ground_truth/`
- Blank IRS form PDFs from `/templates/`

**Processing Logic:**
- Extract field names from blank IRS form AcroForms using pypdf
- OCR the 2024 filed return to extract ground truth values
- One Ollama call to build the mapping: source JSON field → IRS form field name → ground truth value
- Output is a reusable mapping template for future years

**Outputs:**
- `mapping_template.json` — reusable field mapping for each form
- `ground_truth.json` — expected values from 2024 filed return (used for validation)

---

### Step 4: Form Populator (llama3.1:8b)

**Inputs:**
- All formatted JSON from Step 2
- `mapping_template.json` from Step 3

**Processing Logic:**
- One Ollama call per IRS form
- Model receives: formatted source JSON + mapping template + IRS field list
- Model outputs: populated field values JSON for that form
- ESPP / Form 8949: explicit prompt instructions on cost basis adjustment and W-2
  ordinary income exclusion — do NOT double-count

**Outputs:**
- One populated JSON per form saved to `/2024/mapped/populated/`
- Examples: `1040_populated.json`, `schedule_b_populated.json`, `form_8949_populated.json`

---

### Step 5: PDF Filler (pypdf — no LLM)

**Inputs:**
- Blank IRS form PDFs from `/templates/`
- Populated JSON files from Step 4

**Processing Logic:**
- Use pypdf PdfWriter to fill AcroForm fields by field name
- Field names from `mapping_template.json` match pypdf field names exactly
- Flatten the PDF after filling (fields become printed, not interactive)
- One output PDF per form

**Outputs:**
- Completed IRS form PDFs in `/2024/output/`
- Examples: `1040_filled.pdf`, `schedule_b_filled.pdf`, `form_8949_filled.pdf`
- Combined: `all_forms.pdf` merging all forms into one file

---

## 7. Logging Specification

Every session saves a complete log. Logs are never deleted automatically.

| Attribute | Detail |
|-----------|--------|
| Log file location | `/2024/logs/run_YYYYMMDD_HHMMSS.json` |
| Format | JSON — structured, machine-readable |
| What is logged | Every step: inputs, outputs, LLM prompts, LLM raw responses, user edits, approvals, rejections, errors, timestamps |
| Manual edits | Field name, LLM original value, user-entered value, timestamp |
| LLM uncertainty flags | Field name, LLM confidence note, user resolution (confirmed / corrected / skipped) |
| Errors | Full error message, traceback, file name, step number |
| Session summary | Steps completed, fields edited, flags resolved, output files written |

---

## 8. Error Handling

### 8.1 Priority Edge Cases

#### Missing Fields in a Source Document
- LLM sets the field value to `null` in the output JSON
- UI flags the field with a yellow warning at the review checkpoint
- User is prompted to enter the value manually or mark as "not applicable"
- Pipeline does not halt — continues with null flagged for resolution

#### Corrupted or Unreadable PDF
- pdfplumber raises exception OR returns empty string
- pytesseract fallback is attempted automatically
- If both fail: file marked as "extraction failed" in `extraction_summary.json`
- Red error card shown in UI with filename and suggested action
- User can manually type extracted values into the Step 2 JSON editor
- Pipeline continues for all other documents — does not halt on one failure

#### LLM Returns Malformed JSON
- First attempt: auto-retry with stricter prompt ("return ONLY a JSON object, no other text")
- Second attempt: if still malformed, log the raw LLM output
- UI shows raw output and a JSON text editor for the user to manually fix
- User can paste corrected JSON and approve manually
- Fixed JSON saved with `"manually_repaired": true` flag in the log

### 8.2 Additional Error Conditions

| Error Condition | Handling |
|-----------------|----------|
| Ollama not running | Show error: "Ollama is not running. Please start Ollama from your system tray and try again." |
| Model not pulled | Show error with the exact `ollama pull` command to run |
| Duplicate document uploaded | Detect by filename similarity — warn user and ask to confirm or replace |
| Wrong tax year document | Prompt user to confirm tax year shown on document before processing |
| PDF has no AcroForm fields | Warn user — PDF filler cannot write to flat/scanned PDFs. Suggest downloading official fillable IRS PDF. |

---

## 9. Windows Setup Guide (Step-by-Step)

Complete this setup once before running the tool for the first time. Follow in order.

### 9.1 Install Python
1. Go to https://www.python.org/downloads/ and download Python 3.11 or later
2. Run the installer — **CRITICAL: check "Add Python to PATH"** before clicking Install
3. Verify: open Command Prompt and run `python --version`
4. Expected: `Python 3.11.x` or later

### 9.2 Install Tesseract OCR
1. Go to https://github.com/UB-Mannheim/tesseract/wiki and download the Windows installer
2. Run the installer — note the install path (default: `C:\Program Files\Tesseract-OCR\`)
3. Add Tesseract to PATH: Start → "Environment Variables" → System Variables → Path → Edit → New → paste install path
4. Verify in a new Command Prompt: `tesseract --version`

### 9.3 Install Ollama
1. Go to https://ollama.com/download and download the Windows installer
2. Run the installer — Ollama installs as a background service (system tray icon)
3. Verify: `ollama --version`
4. Pull required models (10–30 minutes depending on internet speed):
   ```
   ollama pull llama3.1:8b
   ollama pull deepseek-r1:7b
   ```
5. Verify models are available: `ollama list`

> **Storage note:** llama3.1:8b is ~4.7GB. deepseek-r1:7b is ~4.7GB.
> Ensure at least 12GB free disk space before pulling.

### 9.4 Install Python Dependencies
1. Navigate to project folder: `cd C:\Users\YourName\Documents\LocalTax`
2. Install: `pip install -r requirements.txt`

**requirements.txt contents:**
```
streamlit
pdfplumber
pytesseract
pdf2image
pypdf
Pillow
requests
```

### 9.5 Install Poppler (required by pdf2image)
1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to `C:\poppler\`
3. Add `C:\poppler\Library\bin` to PATH (same process as Tesseract)
4. Verify in a new Command Prompt: `pdftoppm -v`

### 9.6 Download Blank IRS Forms
1. Go to https://www.irs.gov/forms-instructions
2. Download **fillable PDF versions** of: Form 1040, Schedule 1, Schedule 3, Schedule B, Schedule D, Form 8949, Form 8889
3. Save all to `C:\Users\YourName\Documents\LocalTax\templates\`

> **Important:** Download the fillable/interactive versions (not print versions).
> These contain AcroForm fields that the PDF filler writes to.

### 9.7 Launch the App
1. Open Command Prompt
2. Navigate to project folder: `cd C:\Users\YourName\Documents\LocalTax`
3. Start Streamlit: `streamlit run app.py`
4. Browser opens automatically at `http://localhost:8501`
5. Verify Ollama is running (system tray icon visible)

---

## 10. Build Order & Milestones

> **Target deadline: April 15, 2026.**
> Build in order below. Stop and test at each milestone before proceeding.

| # | Milestone | Description |
|---|-----------|-------------|
| M1 | Project scaffolding | Folder structure, `config.json`, Streamlit app shell with sidebar and step pages |
| M2 | Step 1 — OCR | pdfplumber + pytesseract pipeline, auto-detect logic, `extraction_summary.json` |
| M3 | Step 2 — Formatter | Ollama integration, JSON schema templates for all document types, malformed JSON retry |
| M4 | Step 5 — PDF Filler | pypdf form filling, AcroForm field mapping validation on blank IRS forms |
| M5 | Schedule B + 1040 basic | First end-to-end: W-2 + 1099-INT → Schedule B → 1040 lines |
| M6 | Form 8889 (HSA) | 1099-SA + 5498 → Form 8889 end-to-end |
| M7 | Schedule D + Form 8949 | 3922 + 1099-B → ESPP cost basis handling → Form 8949 → Schedule D |
| M8 | Step 3 — Mapping Builder | Ground truth extraction from 2024 filed return, `mapping_template.json` |
| M9 | Validation run | Full pipeline on 2024 docs, compare output against filed return, fix discrepancies |
| M10 | Prior year comparison UI | Diff view in Step 4 review screen, threshold flagging |
| M11 | Polish + logging | Complete session logging, all error handling, UI edge cases |

---

## 11. Testing Strategy

### 11.1 Ground Truth Validation

- Use 2024 source documents as pipeline inputs
- Use 2024 filed return as ground truth (Step 3 output)
- Compare every populated IRS form field value against the ground truth
- Track: exact matches, close matches (within $1 rounding), and mismatches
- A mismatch report is generated after each full pipeline run
- **Target before live use:** 100% match on all dollar-value fields, 0 unexplained mismatches

### 11.2 Test Cases Per Form

| Form | Key Validation Points |
|------|-----------------------|
| Schedule B | Interest from 1099-INT matches line 1; dividends from 1099-DIV match line 5; totals carry to 1040 |
| Form 8889 | HSA contributions from 5498 match line 2; distributions from 1099-SA match line 14a; deduction carries to Schedule 1 |
| Form 8949 | Each ESPP row: correct proceeds, adjusted cost basis (W-2 ordinary income added), correct gain/loss |
| Schedule D | Short-term and long-term totals from 8949 carry correctly; net gain/loss carries to 1040 |
| Form 1040 | All income lines populated; all deductions applied; final tax owed matches 2024 filed return |

### 11.3 OCR Quality Testing

- Test pdfplumber on each digital PDF — verify character accuracy against visual inspection
- Test pytesseract on each scanned document — flag documents where accuracy is poor
- For scanned documents with poor OCR: note which ones require manual field entry

---

## 12. Security & Privacy

| Area | Approach |
|------|----------|
| Network access | None required after setup. Ollama runs fully offline. No data leaves the machine. |
| Authentication | None — local only. Streamlit UI accessible only on localhost (127.0.0.1). |
| Source PDF storage | Kept as-is (unencrypted) in project folder. User responsible for folder-level access. |
| Output PDF storage | Kept as-is (unencrypted) in `/output/`. Treat like any sensitive financial document. |
| Log files | Contain extracted values including income and SSN last 4 digits. Keep logs folder secured. |
| LLM data handling | All prompts and responses stay local via Ollama. No telemetry. No cloud. |
| Backup recommendation | Back up the entire project folder to an encrypted external drive after each tax season. |

---

## 13. Phase 2 — California State Taxes (Placeholder)

> **Phase 2 is not in scope for the April 2026 deadline.**
> Do not begin Phase 2 until Phase 1 is fully validated against the 2024 federal return.

Phase 2 will add support for:
- Form 540 — California Resident Income Tax Return
- Schedule CA (540) — California Adjustments to Income
- Schedule D (540) — California Capital Gain or Loss Adjustment

Phase 2 dependencies:
- Phase 1 federal pipeline must be complete and validated
- California FTB fillable PDF forms must be sourced and field-mapped
- Additional LLM prompt templates for CA-specific adjustments (conformity differences with federal)
- CA Schedule D differences from federal Schedule D must be explicitly handled

---

## 14. Open Questions & Decisions Deferred

| Question | Notes |
|----------|-------|
| Final PDF output format | Print-only vs. e-file ready. To be decided once pipeline is validated. |
| Threshold for "big difference" flag | Defaulting to 20% year-over-year change. May need tuning after first validation run. |
| Handling of 1095-C | ACA form — confirm whether any fields are needed for 1040 or Form 8962. |
| 5498 timing | 5498 is often issued after the April filing deadline. Pipeline must handle it being absent. |
| Model versions | Document the exact Ollama model versions used for reproducibility. |

---

*End of Document — LocalTax PRD v1.0*