import json
from pathlib import Path

import streamlit as st

CONFIG_PATH = Path(__file__).parent / "config.json"
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


def init_session_state():
    if "active_step" not in st.session_state:
        st.session_state.active_step = 1
    for step in STEPS:
        key = f"step_{step['id']}_status"
        if key not in st.session_state:
            st.session_state[key] = "not_started"


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

    st.info("Pipeline logic for this step has not been implemented yet. This is the M1 skeleton.")


def main():
    st.set_page_config(page_title="LocalTax", layout="wide")
    init_session_state()
    render_sidebar()

    active_step = next(s for s in STEPS if s["id"] == st.session_state.active_step)
    render_step_page(active_step)


if __name__ == "__main__":
    main()
