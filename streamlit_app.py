import base64
import mimetypes
import os
import re
import sys
from pathlib import Path

import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent
PROTOTYPE_DIR = ROOT_DIR / "Prototypes" / "v.1.2 django adaptation"
STATIC_DIR = PROTOTYPE_DIR / "eras" / "static"

sys.path.insert(0, str(PROTOTYPE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eras_project.settings")

import django  # noqa: E402
from django.template.loader import render_to_string  # noqa: E402


django.setup()


def static_file_to_data_uri(relative_path):
    file_path = STATIC_DIR / relative_path
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def read_static_text(relative_path):
    return (STATIC_DIR / relative_path).read_text(encoding="utf-8")


def inline_assets(html):
    html = re.sub(
        r'<link rel="icon" href="static/(.*?)">',
        lambda match: f'<link rel="icon" href="{static_file_to_data_uri(match.group(1))}">',
        html,
    )
    html = re.sub(
        r'<link rel="stylesheet" href="static/(.*?)">',
        lambda match: f"<style>\n{read_static_text(match.group(1))}\n</style>",
        html,
    )

    def inline_script(match):
        script = read_static_text(match.group(1))
        script = script.replace(
            "window.location.href = checklistUrl(patient);",
            """
  const params = new URLSearchParams();
  params.set("view", "checklist");
  params.set("patient", patient.name || "");
  params.set("case", patient.caseNumber || "");
  params.set("opdate", patient.opDate || "");
  window.parent.location.search = params.toString();
            """.strip(),
        )
        return f"<script>\n{script}\n</script>"

    html = re.sub(r'<script src="static/(.*?)" defer></script>', inline_script, html)
    return html


def render_django_page(template_name, page_title):
    html = render_to_string(template_name, {"page_title": page_title})
    return inline_assets(html)


st.set_page_config(page_title="BENE Plattform", layout="wide")

query_params = st.query_params
initial_view = "Checklist" if query_params.get("view") == "checklist" else "Patientenuebersicht"

with st.sidebar:
    st.title("BENE Plattform")
    selected_page = st.radio(
        "Seite",
        ["Patientenuebersicht", "Checklist"],
        index=["Patientenuebersicht", "Checklist"].index(initial_view),
    )

if selected_page == "Patientenuebersicht":
    page_html = render_django_page(
        "eras/pages/home.html",
        "BENE Plattform - Frontpage V1.1",
    )
else:
    page_html = render_django_page(
        "eras/pages/checklist.html",
        "BENE Plattform",
    )

st.html(page_html, unsafe_allow_javascript=True)
