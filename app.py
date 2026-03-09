import json
from pathlib import Path

import streamlit as st

import ocr

# ---------------------------------------------------------------------------
# Config & constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.json"
with open(CONFIG_PATH) as f:
    config = json.load(f)

STEPS = [
    {
        "id": 1,
        "name": "Step 1 — OCR Extraction",
        "model": None,
        "description": "Extract text from source PDFs using pdfplumber (digital) or pytesseract (scanned).",
        "inputs": f"{config['tax_year']}/input/",
        "outputs": f"{config['tax_year']}/extracted/",
    },
    {
        "id": 2,
        "name": "Step 2 — LLM Formatter",
        "model": config["models"]["formatter"],
        "description": "Structure raw extracted text into validated JSON using a local LLM.",
        "inputs": f"{config['tax_year']}/extracted/",
        "outputs": f"{config['tax_year']}/mapped/formatted/",
    },
    {
        "id": 3,
        "name": "Step 3 — Mapping Builder",
        "model": config["models"]["mapping_builder"],
        "description": "Build IRS form field mappings from prior year return using a local LLM.",
        "inputs": f"{config['tax_year']}/mapped/formatted/ + {config['tax_year']}/ground_truth/",
        "outputs": f"{config['tax_year']}/mapped/mapping_template.json",
    },
    {
        "id": 4,
        "name": "Step 4 — Form Populator",
        "model": config["models"]["populator"],
        "description": "Populate IRS form field values from structured JSON and field mappings.",
        "inputs": f"{config['tax_year']}/mapped/formatted/ + mapping_template.json",
        "outputs": f"{config['tax_year']}/mapped/populated/",
    },
    {
        "id": 5,
        "name": "Step 5 — PDF Filler",
        "model": None,
        "description": "Write populated field values into blank IRS fillable PDF forms using pypdf.",
        "inputs": f"{config['tax_year']}/mapped/populated/ + templates/",
        "outputs": f"{config['tax_year']}/output/",
    },
]

STATUS_LABELS = {
    "not_started": "Not started",
    "complete": "Complete — pending approval",
    "approved": "Approved",
}

STATUS_COLORS = {
    "not_started": "gray",
    "complete": "orange",
    "approved": "green",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_path(key: str, year: str = None) -> Path:
    """Resolve a config path key to an absolute Path for the given tax year."""
    year = year or config["tax_year"]
    return ROOT / config["paths"][key].replace("{year}", year)


def tesseract_cmd() -> str | None:
    val = config.get("tesseract_cmd", "").strip()
    return val if val else None


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def init_session_state():
    if "active_step" not in st.session_state:
        st.session_state.active_step = 1
    for step in STEPS:
        key = f"step_{step['id']}_status"
        if key not in st.session_state:
            st.session_state[key] = "not_started"
    if "step_1_results" not in st.session_state:
        st.session_state.step_1_results = None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar():
    st.sidebar.title("LocalTax")
    st.sidebar.markdown(f"**Tax Year:** {config['tax_year']}")
    st.sidebar.markdown("---")
    st.sidebar.subheader("Pipeline")

    for step in STEPS:
        status = st.session_state[f"step_{step['id']}_status"]
        label = STATUS_LABELS[status]
        color = STATUS_COLORS[status]
        is_active = st.session_state.active_step == step["id"]

        button_label = f"{'> ' if is_active else ''}{step['name']}"
        if st.sidebar.button(button_label, key=f"nav_{step['id']}", use_container_width=True):
            st.session_state.active_step = step["id"]
            st.rerun()

        st.sidebar.markdown(
            f"<small style='color:{color}; padding-left: 8px;'>{label}</small>",
            unsafe_allow_html=True,
        )

    st.sidebar.markdown("---")
    active_step = next(s for s in STEPS if s["id"] == st.session_state.active_step)
    model_display = active_step["model"] if active_step["model"] else "Python only (no LLM)"
    st.sidebar.markdown(f"**Active model:** `{model_display}`")


# ---------------------------------------------------------------------------
# Step 1 — OCR Extraction
# ---------------------------------------------------------------------------

def render_step_1():
    input_dir = get_path("input")
    output_dir = get_path("extracted")

    st.header("Step 1 — OCR Extraction")
    st.caption(
        "Extracts text from source PDFs. "
        "Uses pdfplumber for digital PDFs; falls back to pytesseract for scanned documents."
    )
    st.markdown(
        f"**Input:** `{input_dir.relative_to(ROOT)}`  "
        f"**Output:** `{output_dir.relative_to(ROOT)}`"
    )
    st.divider()

    # --- File uploader ---
    uploaded_files = st.file_uploader(
        "Upload source PDFs (W-2, 1099s, etc.)",
        type="pdf",
        accept_multiple_files=True,
        help="Files are saved to the input folder. Re-uploading a file with the same name overwrites it.",
    )
    if uploaded_files:
        input_dir.mkdir(parents=True, exist_ok=True)
        for f in uploaded_files:
            (input_dir / f.name).write_bytes(f.read())
        st.success(f"Saved {len(uploaded_files)} file(s) to `{input_dir.relative_to(ROOT)}`")

    # --- Queue ---
    pdf_files = sorted(input_dir.glob("*.pdf")) if input_dir.exists() else []

    if not pdf_files:
        st.warning("No PDFs found in the input folder. Upload files above to begin.")
        return

    st.markdown(f"**{len(pdf_files)} PDF(s) queued for extraction:**")
    for p in pdf_files:
        st.markdown(f"- `{p.name}`")

    st.markdown("")

    # --- Run button ---
    if st.button("Run Step 1 — Extract Text", type="primary"):
        progress = st.progress(0, text="Starting extraction...")
        results = []
        for i, pdf_path in enumerate(pdf_files):
            progress.progress(
                (i + 1) / len(pdf_files),
                text=f"Extracting `{pdf_path.name}` ({i + 1}/{len(pdf_files)})...",
            )
            result = ocr.extract_single_pdf(
                pdf_path,
                min_chars=config["thresholds"]["ocr_min_chars"],
                tesseract_cmd=tesseract_cmd(),
            )
            # Write .txt immediately so partial results are saved if a later file errors
            if result["error"] is None and result["text"]:
                output_dir.mkdir(parents=True, exist_ok=True)
                out_name = pdf_path.stem.lower().replace(" ", "_") + ".txt"
                (output_dir / out_name).write_text(result["text"], encoding="utf-8")
                result["output_file"] = out_name
            results.append(result)

        # Write extraction_summary.json
        output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = output_dir / "extraction_summary.json"
        summary_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

        st.session_state.step_1_results = results
        st.session_state.step_1_status = "complete"
        progress.empty()
        st.rerun()

    # --- Review panel ---
    results = st.session_state.step_1_results

    # Also load from disk if results exist on disk but not in session (e.g. after page refresh)
    if results is None:
        summary_path = output_dir / "extraction_summary.json"
        if summary_path.exists():
            with open(summary_path) as f:
                results = json.load(f)
            st.session_state.step_1_results = results

    if results is None:
        return

    st.divider()
    st.subheader("Extraction Results")

    # Summary table
    failed = [r for r in results if r["error"]]
    warned = [r for r in results if r["warnings"] and not r["error"]]
    ok = [r for r in results if not r["error"] and not r["warnings"]]

    col1, col2, col3 = st.columns(3)
    col1.metric("Extracted OK", len(ok))
    col2.metric("Warnings", len(warned))
    col3.metric("Failed", len(failed))

    if failed:
        st.error(
            f"{len(failed)} file(s) could not be extracted and will be skipped. "
            "You can manually enter their values in Step 2."
        )

    st.markdown("")

    # Per-document expandable previews
    for result in results:
        warnings = result.get("warnings", [])
        err = result.get("error")

        if err:
            label = f"[FAILED] {result['filename']}"
        elif warnings:
            label = f"[WARNING] {result['filename']}"
        else:
            label = f"[OK] {result['filename']}"

        with st.expander(label, expanded=bool(err or warnings)):
            col_a, col_b, col_c = st.columns(3)
            col_a.markdown(f"**Method:** `{result['method'] or '—'}`")
            col_b.markdown(f"**Pages:** {result['page_count']}")
            col_c.markdown(f"**Characters:** {result['char_count']:,}")

            if warnings:
                for w in warnings:
                    st.warning(w)

            if err:
                st.error(f"**Error:** {err}")
            elif result["text"]:
                st.text_area(
                    "Extracted text (read-only preview)",
                    value=result["text"],
                    height=200,
                    disabled=True,
                    key=f"preview_{result['filename']}",
                )
            else:
                st.warning("No text was extracted from this file.")

    # --- Approve / Re-run controls ---
    st.divider()
    status = st.session_state.step_1_status

    if status == "approved":
        st.success("Step 1 approved. Proceed to Step 2.")
    else:
        col_approve, col_rerun = st.columns([2, 1])
        with col_approve:
            if st.button(
                "Approve Step 1 — Proceed to Step 2",
                type="primary",
                disabled=bool(failed),
                help="Cannot approve while files have extraction errors." if failed else None,
            ):
                st.session_state.step_1_status = "approved"
                st.rerun()
        with col_rerun:
            if st.button("Re-run extraction"):
                st.session_state.step_1_results = None
                st.session_state.step_1_status = "not_started"
                st.rerun()


# ---------------------------------------------------------------------------
# Generic placeholder — steps 2–5
# ---------------------------------------------------------------------------

def render_step_page(step):
    st.header(step["name"])
    st.caption(step["description"])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Input:** `{step['inputs']}`")
    with col2:
        st.markdown(f"**Output:** `{step['outputs']}`")

    st.divider()

    status = st.session_state[f"step_{step['id']}_status"]
    color = STATUS_COLORS[status]
    label = STATUS_LABELS[status]
    st.markdown(
        f"**Status:** <span style='color:{color}'>{label}</span>",
        unsafe_allow_html=True,
    )

    st.info("Pipeline logic for this step has not been implemented yet.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="LocalTax", layout="wide")
    init_session_state()
    render_sidebar()

    active_step = next(s for s in STEPS if s["id"] == st.session_state.active_step)

    if active_step["id"] == 1:
        render_step_1()
    else:
        render_step_page(active_step)


if __name__ == "__main__":
    main()
