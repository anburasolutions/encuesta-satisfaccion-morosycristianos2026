from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets as pysecrets
from datetime import datetime
from typing import Any
from textwrap import wrap
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import Client, create_client
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether, HRFlowable

# =============================================================
# CONFIGURACIÓN GENERAL
# =============================================================

APP_TITLE = "Encuesta Moros y Cristianos Aspe 2026"
ORG_NAME = "Unión de Moros y Cristianos Virgen de las Nieves · Junta Central"
LOGO_PATH = "assets/escudo_union_moros_cristianos.jpg"
COMPARSAS_BG_PATH = "assets/comparsa_background.png"

COMPARSAS = [
    "Moros Alcaná",
    "Moros Aljau",
    "Moros Fauquíes",
    "Moros Sulaymán",
    "Cristianos Contrabandistas de la Sierra Negra",
    "Cristianos Duque de Maqueda",
    "Cristianos Estudiantes",
    "Cristianos Lanceros de Uchel",
]

# Totales oficiales de comparsistas adultos.
# Se usan también como respaldo visual si la lectura de Supabase falla temporalmente.
OFFICIAL_COMPARSISTAS = {
    "Moros Alcaná": 113,
    "Moros Aljau": 153,
    "Moros Fauquíes": 195,
    "Moros Sulaymán": 109,
    "Cristianos Contrabandistas de la Sierra Negra": 319,
    "Cristianos Duque de Maqueda": 225,
    "Cristianos Estudiantes": 214,
    "Cristianos Lanceros de Uchel": 329,
}

EDADES = [
    "Menos de 18 años",
    "18–30 años",
    "31–45 años",
    "46–60 años",
    "Más de 60 años",
]

ANTIGUEDADES = [
    "Es mi primer año",
    "2–5 años",
    "6–10 años",
    "11–20 años",
    "Más de 20 años",
]

CARGOS = [
    "No",
    "Sí, cargo festero",
    "Sí, responsabilidad en mi comparsa",
    "Sí, responsabilidad en Junta Central",
    "Otro",
    "Prefiero no indicarlo",
]

ACTOS = {
    "acto_presentacion": "Presentación de Cargos al Alcalde",
    "acto_pregon": "Proclamación de Cargos y Pregón",
    "acto_bandas": "Entrada de Bandas / Pasacalles Autoridades",
    "acto_retreta": "Retreta",
    "acto_pasacalles": "Pasacalles Festero",
    "acto_entrada_mora": "Entrada Mora",
    "acto_guerrilla": "Guerrilla",
    "acto_residencia": "Pasacalle y desfile en Residencia de Ancianos",
    "acto_misa": "Misa Festera",
    "acto_embajada": "Embajada",
    "acto_entrada_cristiana": "Entrada Cristiana",
    "acto_premios": "Fallo Premios Miguel Iborra y Entrega de Banderas",
}

ACTOS_PREGUNTAS = {
    "acto_presentacion": "Presentación de Cargos al Alcalde (día 4)",
    "acto_pregon": "Proclamación de Cargos y Pregón (día 4)",
    "acto_bandas": "Entrada de Bandas / Pasacalles Autoridades (día 7)",
    "acto_retreta": "Retreta (día 7)",
    "acto_pasacalles": "Pasacalles Festero (día 8)",
    "acto_entrada_mora": "Entrada Mora (día 8)",
    "acto_guerrilla": "Guerrilla (día 9)",
    "acto_residencia": "Pasacalle y desfile en Residencia de Ancianos (día 9)",
    "acto_misa": "Misa Festera (día 9)",
    "acto_embajada": "Embajada (día 9)",
    "acto_entrada_cristiana": "Entrada Cristiana (día 10)",
    "acto_premios": "Fallo Premios Miguel Iborra y Entrega de Banderas (día 10)",
}

ACTO_CHOICES = list(ACTOS.values()) + ["Ninguno en particular"]
RATING_OPTIONS = ["1 · Muy mal", "2 · Mal", "3 · Regular", "4 · Bien", "5 · Muy bien", "No asistí / No puedo valorarlo"]

TOTAL_STEPS = 14

st.set_page_config(page_title=APP_TITLE, page_icon=LOGO_PATH, layout="wide", initial_sidebar_state="expanded")

# =============================================================
# ESTILO
# =============================================================

def image_data_uri(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    mime = "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(file_path.read_bytes()).decode("utf-8")


def build_css() -> str:
    comparsa_bg = image_data_uri(COMPARSAS_BG_PATH)
    return f"""
<style>
/* V21 · Limpieza visual reforzada de la interfaz de Streamlit.
   No altera la encuesta, el panel, los datos ni la lógica. */
#MainMenu {{ visibility: hidden !important; }}
footer {{ visibility: hidden !important; height: 0 !important; }}
[data-testid="stToolbar"] {{ display: none !important; }}
[data-testid="stDecoration"] {{ display: none !important; }}
[data-testid="stStatusWidget"] {{ display: none !important; }}
[data-testid="stHeaderActionElements"] {{ display: none !important; }}
[data-testid="stViewerBadge"] {{ display: none !important; }}
[data-testid="manage-app-button"] {{ display: none !important; }}
[data-testid="stAppDeployButton"] {{ display: none !important; }}
[data-testid="stMainMenu"] {{ display: none !important; }}
[data-testid="stToolbarActions"] {{ display: none !important; }}
[data-testid="stHeaderActionElements"] > * {{ display: none !important; }}
header[data-testid="stHeader"] {{ background: transparent !important; }}
:root {{
    --wine: #641f2a;
    --wine-dark: #43121a;
    --gold: #c5a15a;
    --cream: #fbf8f2;
    --ink: #24201d;
    --muted: #6f685f;
    --line: #e8dfd2;
}}
.stApp {{
    background:
        linear-gradient(rgba(252,250,247,.94), rgba(247,241,231,.96)),
        url('{comparsa_bg}');
    background-size: cover;
    background-position: center top;
    background-repeat: no-repeat;
    background-attachment: fixed;
    color: var(--ink);
}}
.block-container {{
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}}
.survey-shell {{
    max-width: 780px;
    margin: 0 auto;
    backdrop-filter: blur(1px);
}}
.hero {{
    background: linear-gradient(135deg, var(--wine-dark), var(--wine));
    color: white;
    border-radius: 24px;
    padding: 30px 30px 26px 30px;
    box-shadow: 0 18px 42px rgba(67,18,26,.18);
    border: 1px solid rgba(197,161,90,.45);
    margin-bottom: 22px;
}}
.hero .eyebrow {{
    font-size: .78rem;
    letter-spacing: .15em;
    font-weight: 700;
    color: #ead7ab;
    text-transform: uppercase;
    margin-bottom: 10px;
}}
.hero h1 {{
    color: white;
    margin: 0 0 6px 0;
    font-size: clamp(1.8rem, 5vw, 2.8rem);
    line-height: 1.02;
}}
.hero p {{
    color: #f7efe5;
    margin: 8px 0 0 0;
    line-height: 1.55;
}}
.card {{
    background: rgba(255,255,255,.94);
    border: 1px solid var(--line);
    border-radius: 20px;
    padding: 22px 22px 18px 22px;
    box-shadow: 0 8px 30px rgba(65,49,34,.08);
    margin-bottom: 16px;
}}
.section-kicker {{
    color: var(--wine);
    font-weight: 800;
    letter-spacing: .08em;
    text-transform: uppercase;
    font-size: .77rem;
}}
.small-muted {{ color: var(--muted); font-size: .92rem; }}
.privacy-note {{
    background: #f8f2e8;
    border-left: 4px solid var(--gold);
    border-radius: 12px;
    padding: 12px 14px;
    color: #53493f;
    margin: 10px 0 16px 0;
}}
.thanks {{
    text-align: center;
    background: rgba(255,255,255,.96);
    border-radius: 24px;
    padding: 44px 30px;
    border: 1px solid var(--line);
    box-shadow: 0 14px 40px rgba(65,49,34,.08);
}}
.thanks .big {{ font-size: 3rem; }}
.metric-card {{
    border: 1px solid var(--line);
    background: white;
    border-radius: 18px;
    padding: 16px;
    min-height: 110px;
}}
div[data-testid="stMetric"] {{
    background: white;
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 14px 16px;
    box-shadow: 0 6px 22px rgba(65,49,34,.04);
}}
.stButton > button, .stDownloadButton > button {{
    border-radius: 12px !important;
    font-weight: 700 !important;
}}
.stButton > button[kind="primary"] {{
    background: var(--wine) !important;
    border-color: var(--wine) !important;
}}
hr {{ border-color: var(--line) !important; }}

.admin-kpi {{background:#fff;border:1px solid #e7eaf0;border-radius:16px;padding:18px 16px;box-shadow:0 5px 18px rgba(15,30,50,.06);min-height:120px;}}
.admin-kpi .label{{font-size:.78rem;font-weight:800;letter-spacing:.03em;color:#273142;text-transform:uppercase;}}
.admin-kpi .value{{font-size:2rem;font-weight:800;color:#111827;margin-top:6px;}}
.admin-kpi .sub{{font-size:.78rem;color:#667085;margin-top:3px;}}
.dashboard-title{{font-size:2rem;font-weight:900;color:#7c1824;letter-spacing:.02em;margin-bottom:0;}}
.dashboard-sub{{color:#b66a00;font-weight:700;margin-top:-4px;}}
div[data-testid="stSidebar"] {{background:linear-gradient(180deg,#0c2032,#08263d 72%,#0a1d2c);}}
div[data-testid="stSidebar"] * {{color:white;}}
div[data-testid="stSidebar"] div[role="radiogroup"] label {{padding:8px 10px;border-radius:10px;}}
div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{background:rgba(255,255,255,.08);}}
.panel-box{{background:#fff;border:1px solid #e6eaf0;border-radius:18px;padding:18px 18px 15px;box-shadow:0 7px 24px rgba(15,30,50,.055);min-height:100%;}}
.panel-box-title{{font-size:.92rem;font-weight:850;color:#182230;text-transform:uppercase;letter-spacing:.025em;margin-bottom:2px;}}
.panel-box-sub{{font-size:.78rem;color:#667085;margin-bottom:10px;}}
.result-pill{{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:9px 10px;margin:6px 0;background:#f8fafc;border:1px solid #edf0f4;border-radius:10px;}}
.result-pill .answer{{font-weight:650;color:#344054;}}
.result-pill .number{{font-weight:800;color:#7c1824;white-space:nowrap;}}
.kpi-icon{{width:42px;height:42px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--accent-soft);color:var(--accent);font-size:1.25rem;margin-bottom:8px;}}
.ring-card{{background:#fff;border:1px solid #e6eaf0;border-radius:18px;padding:14px;text-align:center;box-shadow:0 7px 24px rgba(15,30,50,.05);min-height:215px;}}
.ring-title{{font-size:.78rem;font-weight:850;color:#253041;text-transform:uppercase;min-height:34px;}}
.ring{{width:108px;height:108px;margin:10px auto;border-radius:50%;background:conic-gradient(var(--ring-color) calc(var(--pct)*1%),#edf1f5 0);display:grid;place-items:center;}}
.ring-inner{{width:76px;height:76px;border-radius:50%;background:#fff;display:grid;place-items:center;font-size:1.45rem;font-weight:900;color:#101828;}}
.ring-sub{{font-size:.78rem;color:#667085;line-height:1.35;}}
.exec-hero{{background:linear-gradient(135deg,#0c2032 0%,#173d58 66%,#7c1824 135%);border-radius:20px;padding:22px 24px;color:white;box-shadow:0 12px 30px rgba(12,32,50,.16);margin:8px 0 18px;}}
.exec-hero .eyebrow{{font-size:.73rem;text-transform:uppercase;letter-spacing:.12em;color:#e8bd69;font-weight:800;}}
.exec-hero .headline{{font-size:1.45rem;font-weight:900;margin-top:6px;line-height:1.18;}}
.exec-hero .subline{{font-size:.88rem;color:#dbe5ed;margin-top:7px;line-height:1.45;}}
.exec-card{{background:#fff;border:1px solid #e5e9ef;border-radius:16px;padding:16px 17px;margin:8px 0;box-shadow:0 5px 18px rgba(16,24,40,.04);}}
.exec-title{{font-size:.86rem;font-weight:900;text-transform:uppercase;letter-spacing:.035em;color:#182230;margin-bottom:10px;}}
.exec-item{{padding:8px 0;border-bottom:1px solid #eef1f4;color:#344054;line-height:1.45;}}
.exec-item:last-child{{border-bottom:0;}}
.exec-good{{border-left:4px solid #3a8f45;}}
.exec-watch{{border-left:4px solid #c98a16;}}
.exec-action{{border-left:4px solid #7c1824;}}
.exec-data{{border-left:4px solid #2d6fba;}}
.simple-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0 18px;}}
.simple-stat{{background:#fff;border:1px solid #e6eaf0;border-radius:17px;padding:16px;box-shadow:0 6px 18px rgba(16,24,40,.05);}}
.simple-stat .label{{font-size:.72rem;font-weight:850;text-transform:uppercase;letter-spacing:.04em;color:#667085;}}
.simple-stat .value{{font-size:1.65rem;font-weight:900;color:#172033;margin-top:5px;}}
.simple-stat .detail{{font-size:.78rem;color:#667085;margin-top:3px;line-height:1.35;}}
.traffic{{background:#fff;border:1px solid #e6eaf0;border-radius:16px;padding:15px 16px;margin:8px 0;box-shadow:0 5px 16px rgba(16,24,40,.04);}}
.traffic.green{{border-left:5px solid #3a8f45;}} .traffic.amber{{border-left:5px solid #d49825;}} .traffic.red{{border-left:5px solid #c84848;}}
.traffic .t-title{{font-size:.82rem;font-weight:900;text-transform:uppercase;letter-spacing:.035em;color:#253041;margin-bottom:6px;}}
.traffic .t-item{{padding:5px 0;color:#344054;line-height:1.42;}}
.simple-decision{{background:#f8fafc;border:1px solid #e9edf2;border-radius:14px;padding:13px 14px;margin:8px 0;}}
.simple-decision strong{{color:#7c1824;}}
@media (max-width: 700px) {{
    .stApp {{
        background:
            linear-gradient(rgba(252,250,247,.97), rgba(247,241,231,.98)),
            url('{comparsa_bg}');
        background-size: cover;
        background-position: center top;
        background-attachment: scroll;
    }}
    .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: .8rem; }}
    .hero {{ padding: 24px 20px; border-radius: 18px; }}
    .card {{ padding: 18px 16px; border-radius: 16px; background: rgba(255,255,255,.97); }}
    .simple-grid {{grid-template-columns:1fr 1fr;}}
}}
</style>
"""

st.markdown(build_css(), unsafe_allow_html=True)


# =============================================================
# UTILIDADES DE CONFIGURACIÓN / DB
# =============================================================

def secret_value(name: str, default: Any = None) -> Any:
    try:
        return st.secrets[name]
    except Exception:
        return default


@st.cache_resource
def get_supabase() -> Client | None:
    url = secret_value("SUPABASE_URL")
    key = secret_value("SUPABASE_PUBLISHABLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_rating(value: str | None) -> int | None:
    if not value or value.startswith("No asistí"):
        return None
    try:
        return int(value.split("·", 1)[0].strip())
    except Exception:
        return None


def validate_invite(raw_token: str | None) -> tuple[bool, str | None, str | None]:
    """Devuelve (válido, comparsa_prefijada, mensaje_error)."""
    require_token = bool(secret_value("REQUIRE_INVITE_TOKEN", False))
    if not require_token:
        return True, None, None
    if not raw_token:
        return False, None, "Este enlace no contiene una invitación válida."
    sb = get_supabase()
    if sb is None:
        return False, None, "La base de datos todavía no está configurada."
    try:
        res = sb.rpc("validate_invitation", {"p_token_hash": hash_token(raw_token)}).execute()
        if not res.data:
            return False, None, "La invitación no es válida."
        row = res.data[0]
        if row.get("used_at"):
            return False, row.get("comparsa"), "Esta invitación ya ha sido utilizada."
        return True, row.get("comparsa"), None
    except Exception:
        return False, None, "No se ha podido comprobar la invitación."


def submit_response(answers: dict[str, Any], raw_token: str | None) -> tuple[bool, str]:
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no está configurado."
    required = ["comparsa", "edad", "antiguedad", "cargo"]
    missing = [key for key in required if not answers.get(key)]
    if missing:
        return False, "No se ha podido enviar porque faltan datos generales de la encuesta. Vuelve al primer paso y comprueba comparsa, edad, antigüedad y cargo."
    try:
        token_hash = hash_token(raw_token) if raw_token else None
        result = sb.rpc(
            "submit_survey",
            {"p_answers": answers, "p_token_hash": token_hash},
        ).execute()
        if result.data:
            return True, "Respuesta registrada correctamente."
        return True, "Respuesta registrada correctamente."
    except Exception as exc:
        text = str(exc)
        if "INVALID_OR_USED_TOKEN" in text:
            return False, "La invitación ya se ha utilizado o no es válida."
        if "MISSING_REQUIRED_SEGMENTATION" in text:
            return False, "Faltan los datos generales (comparsa, edad, antigüedad o cargo). Vuelve al primer paso y complétalos."
        return False, "No se ha podido guardar la respuesta en la base de datos. Inténtalo de nuevo."


def fetch_all_responses() -> pd.DataFrame:
    sb = get_supabase()
    if sb is None:
        return pd.DataFrame()
    user = st.session_state.get("admin_user", "")
    password = st.session_state.get("admin_password", "")
    try:
        res = sb.rpc("admin_get_responses", {"p_username": user, "p_password": password}).execute()
        return flatten_rows(res.data or [])
    except Exception:
        return pd.DataFrame()


def flatten_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    flat: list[dict[str, Any]] = []
    for row in rows:
        ans = row.get("answers") or {}
        record = {
            "id": row.get("id"),
            "created_at": row.get("created_at"),
            "excluded": bool(row.get("excluded", False)),
            **ans,
        }
        for key in ["comparsa", "edad", "antiguedad", "cargo"]:
            if not record.get(key):
                record[key] = row.get(key)
        flat.append(record)
    return pd.DataFrame(flat)


def get_invited_counts() -> dict[str, int]:
    # Los totales oficiales deben estar disponibles siempre, incluso si existe
    # una incidencia puntual al consultar la configuración remota.
    counts = OFFICIAL_COMPARSISTAS.copy()
    sb = get_supabase()
    if sb is None:
        return counts
    try:
        res = sb.rpc("admin_get_comparsa_config", {"p_username": st.session_state.get("admin_user", ""), "p_password": st.session_state.get("admin_password", "")}).execute()
        for row in res.data or []:
            comp = row.get("comparsa")
            if comp in counts:
                remote_value = int(row.get("invited_count") or 0)
                # En producción los 8 totales están configurados. Si por cualquier
                # motivo llegase un cero aislado, conservar el total oficial evita
                # mostrar una participación falsa.
                if remote_value > 0:
                    counts[comp] = remote_value
        return counts
    except Exception:
        return counts


def save_invited_counts(counts: dict[str, int]) -> tuple[bool, str]:
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no está configurado."
    try:
        payload = [{"comparsa": c, "invited_count": int(counts.get(c, 0))} for c in COMPARSAS]
        sb.rpc("admin_save_comparsa_config", {"p_username": st.session_state.get("admin_user", ""), "p_password": st.session_state.get("admin_password", ""), "p_items": payload}).execute()
        return True, "Número de comparsistas actualizado."
    except Exception:
        return False, "No se ha podido guardar la configuración."


def create_invite_links(comparsa: str, quantity: int, base_url: str) -> tuple[bool, pd.DataFrame | None, str]:
    if quantity <= 0:
        return False, None, "Indica un número de enlaces mayor que cero."
    sb = get_supabase()
    if sb is None:
        return False, None, "Supabase no está configurado."
    try:
        raw_tokens = [pysecrets.token_urlsafe(24) for _ in range(quantity)]
        payload = [{"token_hash": hash_token(t), "comparsa": comparsa} for t in raw_tokens]
        sb.rpc("admin_insert_invitations", {
            "p_username": st.session_state.get("admin_user", ""),
            "p_password": st.session_state.get("admin_password", ""),
            "p_items": payload,
        }).execute()
        links = [{"comparsa": comparsa, "enlace": f"{base_url.rstrip('/')}?t={t}"} for t in raw_tokens]
        return True, pd.DataFrame(links), "Enlaces únicos creados correctamente."
    except Exception:
        return False, None, "No se han podido crear los enlaces."

def delete_responses(response_ids: list[str]) -> tuple[bool, str]:
    if not response_ids:
        return False, "Selecciona al menos una encuesta."
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no está configurado."
    try:
        res = sb.rpc("admin_delete_responses", {
            "p_username": st.session_state.get("admin_user", ""),
            "p_password": st.session_state.get("admin_password", ""),
            "p_ids": response_ids,
        }).execute()
        deleted = int(res.data or 0)
        return True, f"Se han borrado {deleted} encuesta(s)."
    except Exception:
        return False, "No se han podido borrar las encuestas seleccionadas."


def delete_all_responses() -> tuple[bool, str]:
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no está configurado."
    try:
        res = sb.rpc("admin_delete_all_responses", {
            "p_username": st.session_state.get("admin_user", ""),
            "p_password": st.session_state.get("admin_password", ""),
        }).execute()
        deleted = int(res.data or 0)
        return True, f"Se han borrado todas las respuestas ({deleted})."
    except Exception:
        return False, "No se han podido borrar todas las respuestas."




def set_responses_excluded(response_ids: list[str], excluded: bool) -> tuple[bool, str]:
    if not response_ids:
        return False, "Selecciona al menos una encuesta."
    sb = get_supabase()
    if sb is None:
        return False, "Supabase no está configurado."
    try:
        result = sb.rpc("admin_set_response_excluded", {
            "p_username": st.session_state.get("admin_user", ""),
            "p_password": st.session_state.get("admin_password", ""),
            "p_ids": response_ids,
            "p_excluded": bool(excluded),
        }).execute()
        count = int(result.data or 0)
        action = "excluidas del análisis" if excluded else "recuperadas para el análisis"
        return True, f"{count} encuesta(s) {action}."
    except Exception:
        return False, "No se ha podido actualizar el estado de las encuestas."

# =============================================================
# ENCUESTA PÚBLICA
# =============================================================

def survey_header(step: int | None = None) -> None:
    st.markdown('<div class="survey-shell">', unsafe_allow_html=True)
    logo_left, logo_center, logo_right = st.columns([1.6, 1, 1.6])
    with logo_center:
        st.image(LOGO_PATH, width=185)
    st.markdown(
        f"""
        <div class="hero">
            <div class="eyebrow">Encuesta de satisfacción</div>
            <h1>Fiestas de Moros y Cristianos de Aspe 2026</h1>
            <p>{ORG_NAME}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if step is not None and step > 0:
        st.progress(step / TOTAL_STEPS, text=f"Paso {step} de {TOTAL_STEPS}")


def survey_footer() -> None:
    st.markdown("---")
    st.markdown(
        '<div class="small-muted" style="text-align:center;line-height:1.5">Encuesta anónima · Responsable: Unión de Moros y Cristianos Virgen de las Nieves de Aspe. Finalidad: conocer la opinión de los festeros y mejorar la organización de las fiestas. No se solicitan datos identificativos directos. Los resultados se tratarán de forma agregada y exclusivamente para fines organizativos y estadísticos internos, conforme al RGPD (UE) 2016/679 y la LOPDGDD 3/2018. Para ejercer los derechos que correspondan en materia de protección de datos, puede dirigirse a la entidad organizadora a través de sus canales oficiales.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)


def init_survey_state() -> None:
    st.session_state.setdefault("survey_step", 0)
    st.session_state.setdefault("survey_done", False)
    st.session_state.setdefault("survey_answers", {})


def persist_answers(*keys: str) -> None:
    """Guarda respuestas fuera del ciclo de vida de los widgets de Streamlit."""
    store = st.session_state.setdefault("survey_answers", {})
    for key in keys:
        if key in st.session_state:
            store[key] = st.session_state.get(key)


def saved_answer(key: str, default: Any = None) -> Any:
    if key in st.session_state:
        return st.session_state.get(key)
    return st.session_state.get("survey_answers", {}).get(key, default)


def nav_buttons(previous: bool = True, next_label: str = "Siguiente", disabled: bool = False) -> tuple[bool, bool]:
    col1, col2 = st.columns([1, 1])
    back_clicked = False
    next_clicked = False
    with col1:
        if previous:
            back_clicked = st.button("← Anterior", use_container_width=True)
    with col2:
        next_clicked = st.button(next_label, type="primary", use_container_width=True, disabled=disabled)
    return back_clicked, next_clicked


def render_survey() -> None:
    init_survey_state()
    raw_token = st.query_params.get("t")
    valid, locked_comparsa, token_error = validate_invite(raw_token)

    if not valid:
        survey_header()
        st.error(token_error or "Invitación no válida.")
        st.info("Si has recibido este enlace por email, comprueba que lo has abierto completo. Si el problema continúa, solicita un nuevo enlace a la organización.")
        survey_footer()
        return

    if st.session_state.survey_done:
        survey_header()
        st.markdown(
            f"""
            <div class="thanks">
                <div class="big">✓</div>
                <h2>¡Muchas gracias por tu participación!</h2>
                <p>Tu respuesta ha quedado registrada.</p>
                <p>Gracias por dedicar unos minutos a ayudarnos a seguir mejorando las Fiestas de Moros y Cristianos de Aspe.</p>
                <p><strong>{ORG_NAME}</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        survey_footer()
        return

    step = int(st.session_state.survey_step)
    survey_header(step if step else None)

    if step == 0:
        st.markdown(
            """
            <div class="card">
                <div class="section-kicker">Bienvenida</div>
                <h2>Tu opinión nos ayuda a mejorar</h2>
                <p>Queremos conocer tu valoración sobre los actos celebrados en 2026 y tu opinión sobre posibles cambios de cara a 2027.</p>
                <div class="privacy-note"><strong>La encuesta es anónima.</strong> No se solicita nombre, email, DNI ni teléfono. <strong>Todas las respuestas que requieren escribir texto son opcionales:</strong> puedes dejarlas en blanco y continuar.</div>
                <p class="small-muted">Duración aproximada: 5–7 minutos.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("COMENZAR ENCUESTA", type="primary", use_container_width=True):
            st.session_state.survey_step = 1
            st.rerun()

    elif step == 1:
        st.markdown('<div class="section-kicker">1 · Datos generales</div><h2>Perfil festero</h2>', unsafe_allow_html=True)
        if locked_comparsa and locked_comparsa in COMPARSAS:
            st.session_state["comparsa"] = locked_comparsa
            st.info(f"Comparsa de la invitación: **{locked_comparsa}**")
        else:
            st.selectbox("¿A qué comparsa perteneces? *", COMPARSAS, key="comparsa", index=None, placeholder="Selecciona tu comparsa")
        st.selectbox("¿Cuál es tu rango de edad? *", EDADES, key="edad", index=None, placeholder="Selecciona una opción")
        st.selectbox("¿Cuántos años llevas participando en las Fiestas? *", ANTIGUEDADES, key="antiguedad", index=None, placeholder="Selecciona una opción")
        st.selectbox("¿Has desempeñado algún cargo o responsabilidad festera durante las Fiestas 2026? *", CARGOS, key="cargo", index=None, placeholder="Selecciona una opción")
        if st.session_state.get("cargo") == "Otro":
            st.text_input("Si quieres, indica cuál (opcional)", key="cargo_otro")
        back, nxt = nav_buttons()
        if back:
            st.session_state.survey_step = 0
            st.rerun()
        if nxt:
            required = [st.session_state.get("comparsa"), st.session_state.get("edad"), st.session_state.get("antiguedad"), st.session_state.get("cargo")]
            if not all(required):
                st.error("Completa las preguntas obligatorias para continuar.")
            else:
                persist_answers("comparsa", "edad", "antiguedad", "cargo", "cargo_otro")
                st.session_state.survey_step = 2
                st.rerun()

    elif step == 2:
        st.markdown('<div class="section-kicker">2 · Valoración general</div><h2>¿Cómo han sido las Fiestas 2026?</h2>', unsafe_allow_html=True)
        st.radio(
            "En una escala del 1 al 5, ¿cómo valorarías el desarrollo general de las Fiestas 2026? *",
            [1, 2, 3, 4, 5],
            horizontal=True,
            key="valoracion_general",
            index=None,
            captions=["Muy mal", "Mal", "Regular", "Bien", "Muy bien"],
        )
        st.selectbox(
            "Pensando en años anteriores, ¿cómo consideras que han evolucionado las Fiestas? *",
            ["Han mejorado mucho", "Han mejorado", "Se mantienen aproximadamente igual", "Han empeorado", "Han empeorado mucho", "No puedo valorarlo"],
            key="evolucion",
            index=None,
            placeholder="Selecciona una opción",
        )
        back, nxt = nav_buttons()
        if back:
            st.session_state.survey_step = 1
            st.rerun()
        if nxt:
            if st.session_state.get("valoracion_general") is None or not st.session_state.get("evolucion"):
                st.error("Completa las dos preguntas para continuar.")
            else:
                persist_answers("valoracion_general", "evolucion")
                st.session_state.survey_step = 3
                st.rerun()

    elif step in [3, 4, 5, 6]:
        groups = {
            3: ["acto_presentacion", "acto_pregon", "acto_bandas"],
            4: ["acto_retreta", "acto_pasacalles", "acto_entrada_mora"],
            5: ["acto_guerrilla", "acto_residencia", "acto_misa"],
            6: ["acto_embajada", "acto_entrada_cristiana", "acto_premios"],
        }
        st.markdown(f'<div class="section-kicker">3 · Valoración de los actos</div><h2>Actos · {step-2}/4</h2>', unsafe_allow_html=True)
        st.caption("Valora del 1 al 5. Si no asististe o no puedes valorarlo, elige la última opción. Esa respuesta no se contará como cero.")
        for key in groups[step]:
            st.selectbox(ACTOS_PREGUNTAS[key] + " *", RATING_OPTIONS, key=key + "_ui", index=None, placeholder="Selecciona tu valoración")
        back, nxt = nav_buttons()
        if back:
            st.session_state.survey_step = step - 1
            st.rerun()
        if nxt:
            if any(st.session_state.get(k + "_ui") is None for k in groups[step]):
                st.error("Valora los tres actos para continuar.")
            else:
                for k in groups[step]:
                    st.session_state[k] = normalize_rating(st.session_state.get(k + "_ui"))
                persist_answers(*groups[step])
                st.session_state.survey_step = step + 1
                st.rerun()

    elif step == 7:
        st.markdown('<div class="section-kicker">4 · Tus 3 actos preferidos</div><h2>Elige los 3 actos que más te hayan gustado</h2>', unsafe_allow_html=True)
        st.caption("Elige solo 3 actos y selecciónalos de menos a más: el 1.º será el que menos te gustó de esos tres y el 3.º será el que más te gustó de todos.")
        if len(st.session_state.get("ranking_actos_ui", [])) > 3:
            del st.session_state["ranking_actos_ui"]
        saved_ranking = st.session_state.get("ranking_actos", [])
        if not isinstance(saved_ranking, list) or len(saved_ranking) > 3:
            saved_ranking = []
        ranking = st.multiselect(
            "Elige y ordena tus 3 actos preferidos *",
            list(ACTOS.values()),
            default=saved_ranking,
            max_selections=3,
            key="ranking_actos_ui",
            placeholder="Selecciona 3 actos: de menos a más",
        )
        if ranking:
            st.markdown("**Tu selección actual:**")
            etiquetas = {1: "3.º favorito", 2: "2.º favorito", 3: "1.º favorito · el que más te gustó"}
            for i, acto in enumerate(ranking, 1):
                st.write(f"{i}. {acto} — {etiquetas.get(i, '')}")
        back, nxt = nav_buttons()
        if back:
            st.session_state.survey_step = 6
            st.rerun()
        if nxt:
            if len(ranking) != 3:
                st.error("Para continuar, elige exactamente 3 actos y ordénalos de menos a más.")
            else:
                st.session_state["ranking_actos"] = ranking
                persist_answers("ranking_actos")
                st.session_state.survey_step = 8
                st.rerun()

    elif step == 8:
        st.markdown('<div class="section-kicker">5 · Conclusiones sobre los actos</div><h2>¿Qué destacarías y qué revisarías?</h2>', unsafe_allow_html=True)
        st.selectbox("¿Qué acto destacarías especialmente de forma positiva? *", ACTO_CHOICES, key="acto_destaca", index=None, placeholder="Selecciona una opción")
        st.text_area("Si quieres, cuéntanos brevemente por qué (opcional)", key="acto_destaca_por_que", height=100)
        st.selectbox("¿Qué acto consideras que debería revisarse o mejorarse especialmente? *", ACTO_CHOICES, key="acto_mejorar", index=None, placeholder="Selecciona una opción")
        st.text_area("Si quieres, dinos qué cambiarías (opcional)", key="acto_mejorar_que_cambiarias", height=100)
        st.selectbox(
            "Pensando en el conjunto de las Fiestas, ¿qué opinas de la cantidad de actos? *",
            ["Hay demasiados actos", "La cantidad de actos es adecuada", "Se podrían añadir más actos", "No tengo una opinión clara"],
            key="cantidad_actos",
            index=None,
            placeholder="Selecciona una opción",
        )
        back, nxt = nav_buttons()
        if back:
            st.session_state.survey_step = 7
            st.rerun()
        if nxt:
            if not st.session_state.get("acto_destaca") or not st.session_state.get("acto_mejorar") or not st.session_state.get("cantidad_actos"):
                st.error("Completa las preguntas obligatorias para continuar.")
            else:
                persist_answers("acto_destaca", "acto_destaca_por_que", "acto_mejorar", "acto_mejorar_que_cambiarias", "cantidad_actos")
                st.session_state.survey_step = 9
                st.rerun()

    elif step == 9:
        st.markdown('<div class="section-kicker">6 · Pulsera festera</div><h2>Uso y valoración de la pulsera</h2>', unsafe_allow_html=True)
        st.radio("¿Utilizaste la pulsera festera durante las Fiestas 2026? *", ["Sí", "No"], horizontal=True, key="pulsera_usada_ui", index=None)
        if st.session_state.get("pulsera_usada_ui") == "Sí":
            st.selectbox(
                "¿Te resultó útil y práctica para el control de accesos, identificación, etc.? *",
                ["Sí, totalmente", "En parte", "No, me generó problemas o inconvenientes"],
                key="pulsera_utilidad",
                index=None,
                placeholder="Selecciona una opción",
            )
            st.radio("En una escala del 1 al 5, ¿cómo valorarías la pulsera festera en general? *", [1,2,3,4,5], horizontal=True, key="pulsera_valoracion", index=None)
            st.text_area("¿Qué mejorarías de la pulsera festera? (opcional)", key="pulsera_mejoras", help="Puedes dejar esta respuesta en blanco y continuar.", height=100)
        back, nxt = nav_buttons()
        if back:
            st.session_state.survey_step = 8
            st.rerun()
        if nxt:
            used_ui = st.session_state.get("pulsera_usada_ui")
            if used_ui is None:
                st.error("Indica si utilizaste la pulsera.")
            elif used_ui == "Sí" and (not st.session_state.get("pulsera_utilidad") or st.session_state.get("pulsera_valoracion") is None):
                st.error("Completa la valoración de la pulsera para continuar.")
            else:
                st.session_state["pulsera_usada"] = used_ui == "Sí"
                if used_ui == "No":
                    st.session_state["pulsera_utilidad"] = None
                    st.session_state["pulsera_valoracion"] = None
                    st.session_state["pulsera_mejoras"] = ""
                persist_answers("pulsera_usada", "pulsera_utilidad", "pulsera_valoracion", "pulsera_mejoras")
                st.session_state.survey_step = 10
                st.rerun()

    elif step == 10:
        st.markdown('<div class="section-kicker">7 · Pasacalles Festero</div><h2>Posible cambio de día</h2>', unsafe_allow_html=True)
        st.info("Actualmente el Pasacalles Festero se celebra el día 8 de agosto. Se plantea la posibilidad de trasladarlo al día 7 de agosto.")
        st.radio(
            "¿Qué opción prefieres? *",
            ["Prefiero que pase a celebrarse el día 7", "Prefiero que se mantenga el día 8", "Me resulta indiferente"],
            key="pasacalles_preferencia",
            index=None,
        )
        st.text_area("Si quieres, explica brevemente el motivo de tu respuesta (opcional)", key="pasacalles_motivo", height=110)
        back, nxt = nav_buttons()
        if back:
            st.session_state.survey_step = 9
            st.rerun()
        if nxt:
            if not st.session_state.get("pasacalles_preferencia"):
                st.error("Selecciona una opción para continuar.")
            else:
                persist_answers("pasacalles_preferencia", "pasacalles_motivo")
                st.session_state.survey_step = 11
                st.rerun()

    elif step == 11:
        st.markdown('<div class="section-kicker">8 · Media Fiesta 2027</div><h2>Propuesta de dos días</h2>', unsafe_allow_html=True)
        st.info("Se está valorando organizar la Media Fiesta 2027 así: Día 1 por la noche, Retreta. Día 2, Pasacalles y Entrada de Bandas.")
        st.radio(
            "¿Te gustaría que la Media Fiesta 2027 se organizara de este modo, en dos días? *",
            ["Sí, me parece una buena propuesta", "No, prefiero que se mantenga el formato actual", "Me resulta indiferente"],
            key="media_fiesta_preferencia",
            index=None,
        )
        st.text_area("Sugerencias o comentarios sobre la Media Fiesta 2027 (opcional)", key="media_fiesta_comentarios", height=110)
        back, nxt = nav_buttons()
        if back:
            st.session_state.survey_step = 10
            st.rerun()
        if nxt:
            if not st.session_state.get("media_fiesta_preferencia"):
                st.error("Selecciona una opción para continuar.")
            else:
                persist_answers("media_fiesta_preferencia", "media_fiesta_comentarios")
                st.session_state.survey_step = 12
                st.rerun()

    elif step == 12:
        st.markdown('<div class="section-kicker">9 · Castillo Festero</div><h2>Ubicación del Castillo Festero</h2>', unsafe_allow_html=True)
        st.radio(
            "¿Te gustaría que el Castillo Festero estuviese ubicado en la Avenida de la Constitución? *",
            [
                "Sí, me gustaría que estuviese allí.",
                "No, prefiero que se mantenga en su ubicación actual.",
                "Me es indiferente / No tengo una preferencia clara.",
            ],
            key="castillo_avenida",
            index=None,
        )
        back, nxt = nav_buttons()
        if back:
            st.session_state.survey_step = 11
            st.rerun()
        if nxt:
            if not st.session_state.get("castillo_avenida"):
                st.error("Selecciona una opción para continuar.")
            else:
                persist_answers("castillo_avenida")
                st.session_state.survey_step = 13
                st.rerun()

    elif step == 13:
        st.markdown('<div class="section-kicker">10 · Mirando al futuro</div><h2>Valoración final</h2>', unsafe_allow_html=True)
        st.slider(
            "De 0 a 10, ¿hasta qué punto recomendarías a otro festero participar activamente en las Fiestas de Moros y Cristianos de Aspe? *",
            0, 10, key="recomendacion",
        )
        st.text_area(
            "¿Qué mejorarías de cara a las Fiestas 2027? (opcional)",
            key="mejoras_2027",
            help="Puedes hablarnos de actos, horarios, organización, desfiles, pulsera, convivencia, servicios o cualquier otro aspecto que consideres importante.",
            height=125,
        )
        st.text_area("¿Hay alguna propuesta o comentario que no te hayamos preguntado y quieras trasladar a la Junta Central? (opcional)", key="comentario_final", height=125)
        back, nxt = nav_buttons(next_label="ENVIAR ENCUESTA")
        if back:
            st.session_state.survey_step = 12
            st.rerun()
        if nxt:
            answers = collect_answers()
            ok, msg = submit_response(answers, raw_token)
            if ok:
                st.session_state.survey_done = True
                st.session_state.survey_step = TOTAL_STEPS
                st.rerun()
            else:
                st.error(msg)

    survey_footer()


def collect_answers() -> dict[str, Any]:
    keys = [
        "comparsa", "edad", "antiguedad", "cargo", "cargo_otro",
        "valoracion_general", "evolucion",
        *ACTOS.keys(), "ranking_actos",
        "acto_destaca", "acto_destaca_por_que", "acto_mejorar", "acto_mejorar_que_cambiarias", "cantidad_actos",
        "pulsera_usada", "pulsera_utilidad", "pulsera_valoracion", "pulsera_mejoras",
        "pasacalles_preferencia", "pasacalles_motivo",
        "media_fiesta_preferencia", "media_fiesta_comentarios",
        "castillo_avenida",
        "recomendacion", "mejoras_2027", "comentario_final",
    ]
    persist_answers("recomendacion", "mejoras_2027", "comentario_final")
    return {k: saved_answer(k) for k in keys}

# =============================================================
# ADMIN / PANEL
# =============================================================

def admin_authenticated() -> bool:
    return bool(st.session_state.get("admin_authenticated"))


def render_admin_login() -> bool:
    admin_logo_left, admin_logo_center, admin_logo_right = st.columns([2, 1, 2])
    with admin_logo_center:
        st.image(LOGO_PATH, width=150)
    st.markdown("## Acceso Junta Directiva")
    st.caption("Área privada de resultados y gestión de la encuesta.")
    with st.form("admin_login"):
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if submitted:
        sb = get_supabase()
        ok = False
        try:
            result = sb.rpc("admin_login", {"p_username": user, "p_password": password}).execute() if sb else None
            ok = bool(result and result.data is True)
        except Exception:
            ok = False
        if ok:
            st.session_state.admin_authenticated = True
            st.session_state.admin_user = user
            st.session_state.admin_password = password
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    return False


def apply_filters(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    st.sidebar.markdown("### Filtros")
    selected = {}
    for label, col, options in [
        ("Comparsa", "comparsa", COMPARSAS),
        ("Edad", "edad", EDADES),
        ("Antigüedad", "antiguedad", ANTIGUEDADES),
        ("Cargo / responsabilidad", "cargo", CARGOS),
    ]:
        value = st.sidebar.selectbox(label, ["TODAS"] + options, key=f"f_{col}")
        selected[col] = value
    out = df.copy()
    for col, value in selected.items():
        if value != "TODAS" and col in out.columns:
            out = out[out[col] == value]
    return out, selected


def safe_pct(series: pd.Series, predicate=None) -> float:
    s = series.dropna()
    if len(s) == 0:
        return 0.0
    if predicate is None:
        return float(s.mean() * 100)
    return float(predicate(s).mean() * 100)


def nps_score(series: pd.Series) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return 0.0
    promoters = (s >= 9).mean() * 100
    detractors = (s <= 6).mean() * 100
    return float(promoters - detractors)


def breakdown_counts(df: pd.DataFrame, col: str, labels: dict[Any, str] | None = None) -> pd.DataFrame:
    if col not in df.columns:
        return pd.DataFrame(columns=["Respuesta", "Personas", "Porcentaje"])
    s = df[col].dropna()
    if labels:
        s = s.map(lambda v: labels.get(v, labels.get(str(v), str(v))))
    else:
        s = s.astype(str)
    s = s[s.astype(str).str.strip() != ""]
    counts = s.value_counts(dropna=False)
    total = int(counts.sum())
    rows = []
    for answer, count in counts.items():
        rows.append({"Respuesta": str(answer), "Personas": int(count), "Porcentaje": round((int(count) / total * 100) if total else 0, 1)})
    return pd.DataFrame(rows)


def count_pct(df: pd.DataFrame, col: str, value: Any) -> tuple[int, float]:
    if col not in df.columns:
        return 0, 0.0
    s = df[col].dropna()
    if len(s) == 0:
        return 0, 0.0
    count = int((s == value).sum())
    return count, float(count / len(s) * 100)


def format_count_pct(count: int, pct: float) -> str:
    return f"{count} personas · {pct:.1f}%"


def donut_chart(df: pd.DataFrame, col: str, title: str, labels: dict[Any, str] | None = None):
    counts = breakdown_counts(df, col, labels)
    if counts.empty:
        fig = px.pie(pd.DataFrame({"Respuesta": ["Sin datos"], "Personas": [1]}), names="Respuesta", values="Personas", hole=.58, title=title)
        fig.update_traces(marker=dict(colors=["#e8ecf1"]), textinfo="none", hoverinfo="skip")
        fig.update_layout(showlegend=False, margin=dict(t=55, b=15, l=15, r=15), height=330)
        return fig
    fig = px.pie(counts, names="Respuesta", values="Personas", hole=.58, title=title)
    fig.update_traces(textinfo="value+percent", textposition="inside", hovertemplate="%{label}<br>%{value} personas · %{percent}<extra></extra>")
    fig.update_layout(margin=dict(t=55, b=15, l=15, r=15), legend_title_text="", height=330, font=dict(size=12), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def render_breakdown_list(df: pd.DataFrame, col: str, labels: dict[Any, str] | None = None, limit: int | None = None) -> None:
    table = breakdown_counts(df, col, labels)
    if limit:
        table = table.head(limit)
    if table.empty:
        st.caption("Sin datos todavía.")
        return
    html = []
    for _, row in table.iterrows():
        html.append(f'<div class="result-pill"><span class="answer">{row["Respuesta"]}</span><span class="number">{int(row["Personas"])} · {row["Porcentaje"]:.1f}%</span></div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def render_kpi(column, label: str, value: str, sub: str, icon: str, accent: str = "#7c1824", soft: str = "#f6e9eb") -> None:
    column.markdown(f'<div class="admin-kpi" style="--accent:{accent};--accent-soft:{soft}"><div class="kpi-icon">{icon}</div><div class="label">{label}</div><div class="value">{value}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def render_ring(column, title: str, pct: float | None, sub: str, color: str) -> None:
    safe = 0 if pct is None or pd.isna(pct) else max(0, min(100, float(pct)))
    value = "—" if pct is None or pd.isna(pct) else f"{safe:.0f}%"
    column.markdown(f'<div class="ring-card"><div class="ring-title">{title}</div><div class="ring" style="--pct:{safe:.2f};--ring-color:{color}"><div class="ring-inner">{value}</div></div><div class="ring-sub">{sub}</div></div>', unsafe_allow_html=True)


def nps_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    s = pd.to_numeric(df.get("recomendacion", pd.Series(dtype=float)), errors="coerce").dropna()
    if s.empty:
        return pd.DataFrame(columns=["Respuesta", "Personas", "Porcentaje"])
    groups = pd.Series(np.where(s >= 9, "Promotores (9-10)", np.where(s >= 7, "Pasivos (7-8)", "Detractores (0-6)")))
    counts = groups.value_counts()
    total = len(groups)
    return pd.DataFrame([{"Respuesta": k, "Personas": int(v), "Porcentaje": round(v/total*100,1)} for k,v in counts.items()])


def recent_comment_rows(df: pd.DataFrame, limit: int = 5) -> list[tuple[str, str]]:
    fields = [
        ("comentario_final", "Comentario final"),
        ("mejoras_2027", "Mejoras 2027"),
        ("pasacalles_motivo", "Pasacalles"),
        ("media_fiesta_comentarios", "Media Fiesta"),
        ("pulsera_mejoras", "Pulsera"),
    ]
    working = df.copy()
    working["_date"] = pd.to_datetime(working.get("created_at"), errors="coerce")
    working = working.sort_values("_date", ascending=False)
    result = []
    for _, row in working.iterrows():
        for field, label in fields:
            value = str(row.get(field, "") or "").strip()
            if value and value.lower() != "nan":
                result.append((label, value))
                if len(result) >= limit:
                    return result
    return result

def ranking_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Resume la selección de los 3 actos preferidos.

    La encuesta guarda los tres actos de menos a más preferencia:
    posición 1 = tercero favorito, posición 2 = segundo favorito,
    posición 3 = favorito. Para compatibilidad, si existiera alguna
    respuesta antigua con los 12 actos, se transforma a sus tres
    primeros favoritos del formato anterior.
    """
    stats = {name: {"points": [], "selected": 0, "favorite": 0} for name in ACTOS.values()}
    if "ranking_actos" not in df.columns:
        return pd.DataFrame(columns=["Acto", "Veces elegido", "% de encuestas", "Puntuación media (1-3)", "Puntuación total", "Veces como favorito"])

    valid_rankings = 0
    for value in df["ranking_actos"].dropna():
        ranking = value if isinstance(value, list) else []
        if len(ranking) == 3:
            chosen = ranking
        elif len(ranking) == len(ACTOS):
            # Formato antiguo: estaba ordenado de más a menos. Tomamos los 3 primeros
            # y los invertimos para convertirlos al nuevo formato de menos a más.
            chosen = list(reversed(ranking[:3]))
        else:
            continue
        if len(set(chosen)) != 3:
            continue
        valid_rankings += 1
        for score, name in enumerate(chosen, 1):
            if name in stats:
                stats[name]["selected"] += 1
                stats[name]["points"].append(score)
                if score == 3:
                    stats[name]["favorite"] += 1

    rows = []
    for name, data in stats.items():
        if data["selected"]:
            avg_score = float(np.mean(data["points"]))
            total_points = int(np.sum(data["points"]))
            pct = (data["selected"] / valid_rankings * 100) if valid_rankings else 0.0
            rows.append({
                "Acto": name,
                "Veces elegido": int(data["selected"]),
                "% de encuestas": round(pct, 1),
                "Puntuación media (1-3)": round(avg_score, 2),
                "Puntuación total": total_points,
                "Veces como favorito": int(data["favorite"]),
            })
    if not rows:
        return pd.DataFrame(columns=["Acto", "Veces elegido", "% de encuestas", "Puntuación media (1-3)", "Puntuación total", "Veces como favorito"])
    return pd.DataFrame(rows).sort_values(["Puntuación total", "Veces como favorito", "Veces elegido"], ascending=False)


def acts_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, name in ACTOS.items():
        vals = pd.to_numeric(df.get(key, pd.Series(dtype=float)), errors="coerce").dropna()
        positive = int((vals >= 4).sum()) if len(vals) else 0
        rows.append({
            "Acto": name,
            "Valoración media": round(float(vals.mean()), 2) if len(vals) else np.nan,
            "Respuestas que valoran": int(len(vals)),
            "Valoraciones 4-5 (N)": positive,
            "Valoraciones 4-5 %": round(float((vals >= 4).mean() * 100), 1) if len(vals) else np.nan,
        })
    return pd.DataFrame(rows)


def _pct_count(df: pd.DataFrame, col: str, value: Any) -> tuple[int, float, int]:
    if col not in df.columns:
        return 0, 0.0, 0
    s = df[col].dropna()
    s = s[s.astype(str).str.strip() != ""]
    total = len(s)
    if total == 0:
        return 0, 0.0, 0
    count = int((s == value).sum())
    return count, count / total * 100, total


def _comment_themes(df: pd.DataFrame) -> list[dict[str, Any]]:
    fields = ["acto_destaca_por_que","acto_mejorar_que_cambiarias","pulsera_mejoras","pasacalles_motivo","media_fiesta_comentarios","mejoras_2027","comentario_final"]
    texts=[]
    for field in fields:
        if field in df.columns:
            texts += [str(v).lower().strip() for v in df[field].dropna().tolist() if str(v).strip() and str(v).lower() != "nan"]
    if not texts:
        return []
    themes = {
        "Horarios y duración": ["horario","hora","tarde","noche","duración","duracion","temprano","tarde"],
        "Desfiles y pasacalles": ["desfile","pasacalle","pasacalles","entrada mora","entrada cristiana"],
        "Pulsera y accesos": ["pulsera","acceso","accesos","entrada","control"],
        "Organización": ["organización","organizacion","organizar","coordinación","coordinacion"],
        "Música y bandas": ["música","musica","banda","bandas","charanga"],
        "Media Fiesta": ["media fiesta","retreta"],
        "Convivencia y ambiente": ["convivencia","ambiente","fiesta","festeros","comparsa"],
        "Servicios y espacios": ["baño","baños","aseo","limpieza","agua","barra","barraca","cuartelillo","servicio","servicios"],
    }
    rows=[]
    for name, words in themes.items():
        hits=sum(1 for t in texts if any(w in t for w in words))
        if hits:
            rows.append({"Tema":name,"Menciones":hits,"% comentarios":round(hits/len(texts)*100,1)})
    return sorted(rows,key=lambda x:x["Menciones"],reverse=True)


def executive_interpretation(df: pd.DataFrame, invited: dict[str, int] | None = None, respect_ui_filters: bool = True) -> dict[str, Any]:
    if df.empty:
        return {
            "headline":"Todavía no hay respuestas para elaborar una lectura general.",
            "subline":"El informe se generará automáticamente en cuanto se registren respuestas.",
            "conclusions":[],"strengths":[],"watchouts":[],"actions":[],"evidence":[],"themes":[]
        }

    n=len(df)
    invited=invited or {}
    scope_comparsa = None
    if "comparsa" in df.columns and df["comparsa"].dropna().nunique() == 1:
        scope_comparsa = str(df["comparsa"].dropna().iloc[0])
    demographic_filter_active = respect_ui_filters and any([
        st.session_state.get("top_edad", "Todas") != "Todas",
        st.session_state.get("top_antiguedad", "Todas") != "Todas",
        st.session_state.get("top_cargo", "Todos") != "Todos",
    ])
    total_invited = 0 if demographic_filter_active else (int(invited.get(scope_comparsa,0)) if scope_comparsa else int(sum(invited.values())))
    participation = (n/total_invited*100) if total_invited else None

    avg = pd.to_numeric(df.get("valoracion_general"), errors="coerce").dropna()
    avg_general = float(avg.mean()) if not avg.empty else None
    rec = pd.to_numeric(df.get("recomendacion"), errors="coerce").dropna()
    rec_avg = float(rec.mean()) if not rec.empty else None
    nps = nps_score(rec) if not rec.empty else None

    conclusions=[]; strengths=[]; watchouts=[]; actions=[]; evidence=[]

    if avg_general is not None:
        if avg_general >= 4.25:
            sentiment="muy positiva"
            strengths.append(f"Satisfacción general muy alta: {avg_general:.2f}/5 ({len(avg)} personas la valoraron).")
        elif avg_general >= 3.75:
            sentiment="positiva"
            strengths.append(f"Satisfacción general positiva: {avg_general:.2f}/5 ({len(avg)} valoraciones).")
        elif avg_general >= 3.0:
            sentiment="moderada"
            watchouts.append(f"La satisfacción general es moderada ({avg_general:.2f}/5); conviene revisar qué áreas están frenando una valoración más alta.")
        else:
            sentiment="claramente mejorable"
            watchouts.append(f"La valoración general es baja ({avg_general:.2f}/5) y requiere un plan de mejora prioritario.")
        conclusions.append(f"La percepción global de las Fiestas es {sentiment}, con una media de {avg_general:.2f} sobre 5.")
        evidence.append(f"Valoración general: {avg_general:.2f}/5 · {len(avg)} respuestas válidas.")

    if participation is not None:
        conclusions.append(f"Han respondido {n} personas de {total_invited} comparsistas ({participation:.1f}% de participación).")
        evidence.append(f"Participación: {n}/{total_invited} · {participation:.1f}%.")
        if participation < 35:
            watchouts.append(f"La participación es limitada ({participation:.1f}%); conviene reforzar recordatorios antes de cerrar conclusiones definitivas.")
            actions.append("Aumentar la participación con uno o dos recordatorios y revisar qué comparsas o perfiles están menos representados.")
        elif participation >= 60:
            strengths.append(f"La participación es alta ({participation:.1f}%), lo que aporta una base sólida para interpretar los resultados.")

    if rec_avg is not None and nps is not None:
        conclusions.append(f"La recomendación media es {rec_avg:.1f}/10 y el NPS es {nps:+.0f}.")
        evidence.append(f"Recomendación: {rec_avg:.1f}/10 · NPS {nps:+.0f} · {len(rec)} respuestas.")
        if nps >= 30:
            strengths.append(f"El NPS es claramente favorable ({nps:+.0f}), señal de una base importante de festeros promotores.")
        elif nps < 0:
            watchouts.append(f"El NPS es negativo ({nps:+.0f}); hay más detractores que promotores y conviene identificar las causas principales.")
            actions.append("Priorizar las causas que aparecen repetidas entre detractores y comentarios abiertos antes de introducir nuevas iniciativas.")

    acts=acts_summary(df).dropna(subset=["Valoración media"]).sort_values("Valoración media",ascending=False)
    if not acts.empty:
        best=acts.iloc[0]; worst=acts.iloc[-1]
        conclusions.append(f"El acto mejor valorado es {best['Acto']} ({best['Valoración media']:.2f}/5) y el de menor media es {worst['Acto']} ({worst['Valoración media']:.2f}/5).")
        strengths.append(f"{best['Acto']} destaca como referencia positiva con {best['Valoración media']:.2f}/5 y {int(best['Valoraciones 4-5 (N)'])} valoraciones de 4 o 5.")
        evidence.append(f"Mejor acto por media: {best['Acto']} · {best['Valoración media']:.2f}/5 · N={int(best['Respuestas que valoran'])}.")
        evidence.append(f"Acto con menor media: {worst['Acto']} · {worst['Valoración media']:.2f}/5 · N={int(worst['Respuestas que valoran'])}.")
        if float(worst['Valoración media']) < 3.75:
            watchouts.append(f"{worst['Acto']} es el acto que más conviene revisar ({worst['Valoración media']:.2f}/5).")
            actions.append(f"Revisar {worst['Acto']} junto con sus comentarios específicos: horario, formato, duración, ubicación y coordinación.")

    rank=ranking_summary(df)
    if not rank.empty:
        top=rank.iloc[0]
        conclusions.append(f"En la elección de los 3 actos favoritos, {top['Acto']} lidera con {int(top['Puntuación total'])} puntos y aparece en el {top['% de encuestas']:.1f}% de las selecciones válidas.")
        evidence.append(f"Favoritos: {top['Acto']} · {int(top['Veces elegido'])} selecciones · {int(top['Veces como favorito'])} veces como nº1.")

    p7_n,p7_pct,p_total=_pct_count(df,"pasacalles_preferencia","Prefiero que pase a celebrarse el día 7")
    p8_n,p8_pct,_=_pct_count(df,"pasacalles_preferencia","Prefiero que se mantenga el día 8")
    ind_n,ind_pct,_=_pct_count(df,"pasacalles_preferencia","Me resulta indiferente")
    if p_total:
        conclusions.append(f"Pasacalles: día 7 obtiene {p7_n} apoyos ({p7_pct:.1f}%), día 8 obtiene {p8_n} ({p8_pct:.1f}%) e indiferente {ind_n} ({ind_pct:.1f}%).")
        evidence.append(f"Pasacalles · día 7: {p7_n} ({p7_pct:.1f}%) · día 8: {p8_n} ({p8_pct:.1f}%) · indiferente: {ind_n} ({ind_pct:.1f}%).")
        if p7_pct >= 55:
            strengths.append(f"Existe una mayoría clara a favor de trasladar el Pasacalles al día 7 ({p7_pct:.1f}%).")
            actions.append("Si se plantea el cambio del Pasacalles, acompañarlo de una comunicación clara de horarios y motivos y revisar los comentarios antes de decidir.")
        elif abs(p7_pct-p8_pct) <= 10:
            watchouts.append("La preferencia entre día 7 y día 8 está relativamente dividida; no conviene basar la decisión únicamente en el porcentaje global.")
            actions.append("Cruzar la preferencia del Pasacalles por comparsa y antigüedad y revisar los motivos escritos antes de tomar una decisión.")

    mf_n,mf_pct,mf_total=_pct_count(df,"media_fiesta_preferencia","Sí, me parece una buena propuesta")
    mf_no,mf_no_pct,_=_pct_count(df,"media_fiesta_preferencia","No, prefiero que se mantenga el formato actual")
    if mf_total:
        conclusions.append(f"Media Fiesta 2027 en dos días: {mf_n} personas están a favor ({mf_pct:.1f}%) y {mf_no} en contra ({mf_no_pct:.1f}%).")
        evidence.append(f"Media Fiesta 2 días · a favor: {mf_n} ({mf_pct:.1f}%) · en contra: {mf_no} ({mf_no_pct:.1f}%).")
        if mf_pct >= 60:
            strengths.append(f"La propuesta de Media Fiesta en dos días cuenta con un apoyo amplio ({mf_pct:.1f}%).")
        elif mf_pct < 45:
            watchouts.append(f"La propuesta de Media Fiesta en dos días no reúne un apoyo mayoritario claro ({mf_pct:.1f}%).")

    pu_n,pu_pct,pu_total=_pct_count(df,"pulsera_usada",True)
    if pu_total:
        evidence.append(f"Uso de pulsera: {pu_n}/{pu_total} · {pu_pct:.1f}%.")
        if pu_pct >= 70:
            strengths.append(f"La pulsera tiene una implantación alta: la utilizó el {pu_pct:.1f}% ({pu_n} personas).")
        elif pu_pct < 50:
            watchouts.append(f"El uso de la pulsera es reducido ({pu_pct:.1f}%); conviene revisar su utilidad, comunicación o funcionamiento.")

    evo=breakdown_counts(df,"evolucion")
    if not evo.empty:
        improved=int(evo[evo['Respuesta'].isin(['Han mejorado mucho','Han mejorado'])]['Personas'].sum())
        worsened=int(evo[evo['Respuesta'].isin(['Han empeorado','Han empeorado mucho'])]['Personas'].sum())
        ev_total=int(evo['Personas'].sum())
        if ev_total:
            imp_pct=improved/ev_total*100; wor_pct=worsened/ev_total*100
            evidence.append(f"Evolución percibida · mejora: {improved} ({imp_pct:.1f}%) · empeora: {worsened} ({wor_pct:.1f}%).")
            if imp_pct >= 50:
                strengths.append(f"La evolución se percibe favorable: {imp_pct:.1f}% considera que las Fiestas han mejorado.")
            if wor_pct >= 30:
                watchouts.append(f"Un {wor_pct:.1f}% percibe empeoramiento respecto a años anteriores; conviene estudiar qué ha cambiado para ese grupo.")

    themes=_comment_themes(df)
    if themes:
        top_theme=themes[0]
        conclusions.append(f"En los comentarios abiertos, el tema recurrente más detectado es “{top_theme['Tema']}” ({top_theme['Menciones']} menciones).")
        evidence.append(f"Comentarios: tema más repetido “{top_theme['Tema']}” · {top_theme['Menciones']} menciones detectadas.")
        actions.append(f"Revisar conjuntamente los comentarios relacionados con “{top_theme['Tema']}”, ya que es el tema que más se repite en las respuestas abiertas.")

    if not actions:
        actions.append("Mantener los elementos mejor valorados y concentrar la revisión en el acto o área con menor valoración media y en los comentarios repetidos.")
    actions.append("Antes de adoptar decisiones definitivas, comparar el resultado total con cada comparsa para detectar diferencias relevantes que la media global pueda ocultar.")

    if avg_general is not None and avg_general >= 4 and (nps is None or nps >= 0):
        headline="Resultado global favorable, con margen para afinar decisiones concretas de 2027."
    elif avg_general is not None and avg_general < 3.5:
        headline="Los resultados señalan varias áreas de mejora que conviene priorizar antes de 2027."
    else:
        headline="La encuesta ofrece una base clara para decidir qué mantener y qué revisar de cara a 2027."
    subline=f"Lectura automática basada en {n} respuestas del filtro actual. Los textos abiertos se usan solo para detectar temas repetidos; la decisión final corresponde a la Junta Directiva."
    return {"headline":headline,"subline":subline,"conclusions":conclusions[:6],"strengths":strengths[:5],"watchouts":watchouts[:5],"actions":actions[:6],"evidence":evidence[:10],"themes":themes[:6]}


def interpretation_points(df: pd.DataFrame, invited: dict[str, int] | None = None) -> list[str]:
    executive=executive_interpretation(df,invited)
    if not executive["conclusions"]:
        return [executive["headline"]]
    return executive["conclusions"] + executive["actions"]


def render_executive_interpretation(df: pd.DataFrame, invited: dict[str, int] | None = None) -> None:
    e=executive_interpretation(df,invited)
    st.markdown(f'<div class="exec-hero"><div class="eyebrow">Interpretación automática</div><div class="headline">{e["headline"]}</div><div class="subline">{e["subline"]}</div></div>',unsafe_allow_html=True)
    if df.empty:
        return
    c1,c2=st.columns(2)
    with c1:
        st.markdown('<div class="exec-card exec-data"><div class="exec-title">Conclusiones principales</div>'+''.join(f'<div class="exec-item">{x}</div>' for x in e["conclusions"])+ '</div>',unsafe_allow_html=True)
        st.markdown('<div class="exec-card exec-good"><div class="exec-title">Fortalezas a mantener</div>'+(''.join(f'<div class="exec-item">{x}</div>' for x in e["strengths"]) if e["strengths"] else '<div class="exec-item">Todavía no hay una fortaleza claramente destacada con los datos actuales.</div>')+'</div>',unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="exec-card exec-watch"><div class="exec-title">Aspectos a revisar</div>'+(''.join(f'<div class="exec-item">{x}</div>' for x in e["watchouts"]) if e["watchouts"] else '<div class="exec-item">No aparece ninguna alerta importante con los datos actuales.</div>')+'</div>',unsafe_allow_html=True)
        st.markdown('<div class="exec-card exec-action"><div class="exec-title">Recomendaciones para 2027</div>'+''.join(f'<div class="exec-item">{x}</div>' for x in e["actions"])+ '</div>',unsafe_allow_html=True)
    st.markdown('<div class="exec-card exec-data"><div class="exec-title">Datos que sustentan la lectura</div>'+''.join(f'<div class="exec-item">{x}</div>' for x in e["evidence"])+ '</div>',unsafe_allow_html=True)
    if e["themes"]:
        st.markdown("#### Temas recurrentes detectados en comentarios")
        st.dataframe(pd.DataFrame(e["themes"]),use_container_width=True,hide_index=True)

def simple_summary_data(df: pd.DataFrame, invited: dict[str, int] | None = None, respect_ui_filters: bool = True) -> dict[str, Any]:
    # Resumen muy sencillo, pensado para leer en 2-3 minutos.
    invited = invited or {}
    n = len(df)
    scope_comparsa = None
    if not df.empty and "comparsa" in df.columns and df["comparsa"].dropna().nunique() == 1:
        scope_comparsa = str(df["comparsa"].dropna().iloc[0])
    demographic_filter_active = respect_ui_filters and any([
        st.session_state.get("top_edad", "Todas") != "Todas",
        st.session_state.get("top_antiguedad", "Todas") != "Todas",
        st.session_state.get("top_cargo", "Todos") != "Todos",
    ])
    total_invited = 0 if demographic_filter_active else (int(invited.get(scope_comparsa, 0)) if scope_comparsa else int(sum(invited.values())))
    participation = (n / total_invited * 100) if total_invited else None

    avg_s = pd.to_numeric(df.get("valoracion_general", pd.Series(dtype=float)), errors="coerce").dropna()
    avg = float(avg_s.mean()) if not avg_s.empty else None
    rec_s = pd.to_numeric(df.get("recomendacion", pd.Series(dtype=float)), errors="coerce").dropna()
    rec = float(rec_s.mean()) if not rec_s.empty else None

    acts = acts_summary(df).dropna(subset=["Valoración media"]).sort_values("Valoración media", ascending=False)
    best_act = None if acts.empty else acts.iloc[0]
    worst_act = None if acts.empty else acts.iloc[-1]
    rank = ranking_summary(df)
    favorite = None if rank.empty else rank.iloc[0]

    p7_n,p7_pct,p_total=_pct_count(df,"pasacalles_preferencia","Prefiero que pase a celebrarse el día 7")
    p8_n,p8_pct,_=_pct_count(df,"pasacalles_preferencia","Prefiero que se mantenga el día 8")
    pi_n,pi_pct,_=_pct_count(df,"pasacalles_preferencia","Me resulta indiferente")
    mf_n,mf_pct,mf_total=_pct_count(df,"media_fiesta_preferencia","Sí, me parece una buena propuesta")
    mf_no,mf_no_pct,_=_pct_count(df,"media_fiesta_preferencia","No, prefiero que se mantenga el formato actual")
    pu_n,pu_pct,pu_total=_pct_count(df,"pulsera_usada",True)

    key_messages=[]
    if avg is not None:
        key_messages.append(f"La valoración general es {avg:.2f}/5, calculada con {len(avg_s)} respuestas válidas.")
    if participation is not None:
        key_messages.append(f"Han respondido {n} de {total_invited} comparsistas ({participation:.1f}%).")
    elif n:
        key_messages.append(f"Se han recibido {n} respuestas. Aún no se ha configurado el total de comparsistas para calcular la participación.")
    if best_act is not None:
        key_messages.append(f"El acto mejor valorado es {best_act['Acto']} ({best_act['Valoración media']:.2f}/5).")
    if favorite is not None:
        key_messages.append(f"El acto que más aparece entre los 3 favoritos es {favorite['Acto']} ({int(favorite['Veces elegido'])} elecciones).")
    if p_total:
        key_messages.append(f"Pasacalles: {p7_n} personas ({p7_pct:.1f}%) prefieren el día 7 y {p8_n} ({p8_pct:.1f}%) el día 8.")
    if mf_total:
        key_messages.append(f"Media Fiesta en dos días: {mf_n} personas ({mf_pct:.1f}%) están a favor y {mf_no} ({mf_no_pct:.1f}%) en contra.")

    green=[]; amber=[]; red=[]; decisions=[]
    if avg is not None:
        if avg >= 4.0: green.append(f"Satisfacción general alta ({avg:.2f}/5).")
        elif avg >= 3.4: amber.append(f"Satisfacción moderada ({avg:.2f}/5): conviene revisar los puntos peor valorados.")
        else: red.append(f"Valoración general baja ({avg:.2f}/5): requiere prioridad de mejora.")
    if best_act is not None:
        green.append(f"Mantener como referencia positiva: {best_act['Acto']} ({best_act['Valoración media']:.2f}/5).")
    if worst_act is not None:
        if float(worst_act['Valoración media']) < 3.5:
            red.append(f"Revisar especialmente {worst_act['Acto']} ({worst_act['Valoración media']:.2f}/5).")
        elif float(worst_act['Valoración media']) < 3.9:
            amber.append(f"Estudiar mejoras en {worst_act['Acto']} ({worst_act['Valoración media']:.2f}/5).")
    if p_total:
        if p7_pct >= 55:
            green.append(f"Hay una mayoría favorable al Pasacalles en día 7: {p7_n} personas ({p7_pct:.1f}%).")
            decisions.append("Pasacalles: la encuesta ofrece una base favorable para estudiar el cambio al día 7.")
        elif p8_pct >= 55:
            green.append(f"Hay una mayoría favorable a mantener el Pasacalles en día 8: {p8_n} personas ({p8_pct:.1f}%).")
            decisions.append("Pasacalles: la encuesta ofrece una base favorable para mantener el día 8.")
        else:
            amber.append(f"El Pasacalles no tiene una mayoría clara: día 7 {p7_pct:.1f}%, día 8 {p8_pct:.1f}%, indiferente {pi_pct:.1f}%.")
            decisions.append("Pasacalles: comparar por comparsa y leer los motivos antes de decidir.")
    if mf_total:
        if mf_pct >= 60:
            green.append(f"Apoyo amplio a la Media Fiesta de dos días: {mf_n} personas ({mf_pct:.1f}%).")
            decisions.append("Media Fiesta 2027: existe apoyo suficiente para desarrollar la propuesta y estudiar detalles de ejecución.")
        elif mf_pct < 45:
            red.append(f"La Media Fiesta de dos días no obtiene apoyo mayoritario ({mf_pct:.1f}%).")
            decisions.append("Media Fiesta 2027: revisar la propuesta antes de avanzar.")
        else:
            amber.append(f"La Media Fiesta de dos días tiene un apoyo intermedio ({mf_pct:.1f}%).")
            decisions.append("Media Fiesta 2027: revisar comentarios y diferencias entre comparsas antes de decidir.")
    if pu_total:
        if pu_pct >= 70: green.append(f"Uso elevado de la pulsera: {pu_n} personas ({pu_pct:.1f}%).")
        elif pu_pct < 50: amber.append(f"Uso limitado de la pulsera: {pu_n} personas ({pu_pct:.1f}%).")
    if participation is not None and participation < 40:
        amber.append(f"Participación todavía limitada ({participation:.1f}%): conviene aumentar respuestas antes de cerrar decisiones.")
    if not decisions:
        decisions.append("Aún no hay datos suficientes para proponer decisiones concretas.")

    themes=_comment_themes(df)
    if themes:
        decisions.append(f"Comentarios: revisar primero el tema “{themes[0]['Tema']}”, que es el más repetido ({themes[0]['Menciones']} menciones).")

    return {
        "n": n, "total_invited": total_invited, "participation": participation,
        "avg": avg, "rec": rec, "key_messages": key_messages[:7],
        "green": green[:5], "amber": amber[:5], "red": red[:5],
        "decisions": decisions[:5], "best_act": best_act, "worst_act": worst_act,
        "favorite": favorite, "p7": (p7_n,p7_pct,p_total), "p8": (p8_n,p8_pct,p_total),
        "media": (mf_n,mf_pct,mf_total), "pulsera": (pu_n,pu_pct,pu_total)
    }


def decision_rows(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    specs=[
        ("Pasacalles Festero", "pasacalles_preferencia", [
            ("Día 7", "Prefiero que pase a celebrarse el día 7"),
            ("Día 8", "Prefiero que se mantenga el día 8"),
            ("Indiferente", "Me resulta indiferente"),
        ]),
        ("Media Fiesta 2027 · 2 días", "media_fiesta_preferencia", [
            ("A favor", "Sí, me parece una buena propuesta"),
            ("En contra", "No, prefiero que se mantenga el formato actual"),
            ("Indiferente", "Me resulta indiferente"),
        ]),
        ("Castillo Festero · Avenida de la Constitución", "castillo_avenida", [
            ("Sí, Avenida de la Constitución", "Sí, me gustaría que estuviese allí."),
            ("No, ubicación actual", "No, prefiero que se mantenga en su ubicación actual."),
            ("Indiferente", "Me es indiferente / No tengo una preferencia clara."),
        ]),
        ("Pulsera festera · utilidad", "pulsera_utilidad", [
            ("Sí, totalmente útil", "Sí, totalmente"),
            ("En parte útil", "En parte"),
            ("No / problemas", "No, me generó problemas o inconvenientes"),
        ]),
    ]
    for tema,col,options in specs:
        valid=df.get(col,pd.Series(dtype=object)).dropna()
        valid=valid[valid.astype(str).str.strip()!=""]
        total=len(valid)
        if not total:
            continue
        for label,value in options:
            count=int((valid==value).sum())
            rows.append({"Tema":tema,"Opción":label,"Personas":count,"Porcentaje":round(count/total*100,1),"N":total})
    return pd.DataFrame(rows)


def render_decisions_page(df: pd.DataFrame) -> None:
    st.markdown("### Decisiones clave para la Junta")
    st.caption("Esta pantalla reúne solo las preguntas que pueden implicar una decisión. Siempre se muestra el número de personas y el porcentaje.")
    data=decision_rows(df)
    if data.empty:
        st.info("Todavía no hay datos suficientes para mostrar decisiones.")
        return
    for tema in data["Tema"].drop_duplicates():
        sub=data[data["Tema"]==tema].copy()
        st.markdown(f"#### {tema}")
        cols=st.columns(len(sub))
        for col,(_,r) in zip(cols,sub.iterrows()):
            col.metric(r["Opción"],f'{int(r["Personas"])} personas',f'{r["Porcentaje"]:.1f}% de N={int(r["N"])}')
        leader=sub.sort_values(["Porcentaje","Personas"],ascending=False).iloc[0]
        second=sub.sort_values(["Porcentaje","Personas"],ascending=False).iloc[1] if len(sub)>1 else None
        margin=leader["Porcentaje"]-(second["Porcentaje"] if second is not None else 0)
        if leader["Porcentaje"]>=60:
            st.success(f'Lectura rápida: **{leader["Opción"]}** tiene un apoyo claro ({leader["Porcentaje"]:.1f}%, {int(leader["Personas"])} personas).')
        elif margin<=10:
            st.warning(f'Lectura rápida: resultado dividido. La opción más elegida es **{leader["Opción"]}** ({leader["Porcentaje"]:.1f}%), pero conviene revisar comparsas y comentarios antes de decidir.')
        else:
            st.info(f'Lectura rápida: **{leader["Opción"]}** es la opción más elegida ({leader["Porcentaje"]:.1f}%), sin alcanzar una mayoría de 60%.')
        st.markdown("---")


def comment_records(df: pd.DataFrame) -> pd.DataFrame:
    fields={
        'acto_destaca_por_que':'Actos · positivo',
        'acto_mejorar_que_cambiarias':'Actos · mejorar',
        'pulsera_mejoras':'Pulsera',
        'pasacalles_motivo':'Pasacalles',
        'media_fiesta_comentarios':'Media Fiesta',
        'mejoras_2027':'Mejoras 2027',
        'comentario_final':'Otros',
    }
    rows=[]
    for _,r in df.iterrows():
        response_id=str(r.get('id','') or '')
        created=pd.to_datetime(r.get('created_at'),errors='coerce')
        fecha='' if pd.isna(created) else created.strftime('%d/%m/%Y %H:%M')
        for field,category in fields.items():
            value=str(r.get(field,'') or '').strip()
            if value and value.lower()!='nan':
                rows.append({
                    "RespuestaID":response_id,
                    "Fecha":fecha,
                    "Categoría":category,
                    "Comentario":value,
                    "Comparsa":r.get('comparsa',''),
                    "Edad":r.get('edad',''),
                })
    return pd.DataFrame(rows)


def comment_theme(text: str) -> str:
    t=str(text).lower()
    themes=[
        ("Horarios y duración",["horario","hora","duración","duracion","temprano","tarde","noche"]),
        ("Desfiles y pasacalles",["desfile","pasacalle","entrada mora","entrada cristiana"]),
        ("Pulsera y accesos",["pulsera","acceso","control"]),
        ("Organización",["organización","organizacion","coordina"]),
        ("Música y bandas",["música","musica","banda","charanga"]),
        ("Servicios y espacios",["baño","aseo","limpieza","agua","barra","barraca","cuartelillo"]),
        ("Convivencia y ambiente",["convivencia","ambiente","festeros","gente joven"]),
    ]
    for name,words in themes:
        if any(w in t for w in words):
            return name
    return "Otros temas"


def comparison_by_comparsa(df: pd.DataFrame) -> pd.DataFrame:
    global_avg=pd.to_numeric(df.get('valoracion_general'),errors='coerce').mean()
    global_p7=count_pct(df,'pasacalles_preferencia','Prefiero que pase a celebrarse el día 7')[1]
    global_mf=count_pct(df,'media_fiesta_preferencia','Sí, me parece una buena propuesta')[1]
    rows=[]
    for comp in COMPARSAS:
        sub=df[df.get('comparsa')==comp]
        if sub.empty:
            continue
        avg=pd.to_numeric(sub.get('valoracion_general'),errors='coerce').mean()
        p7=count_pct(sub,'pasacalles_preferencia','Prefiero que pase a celebrarse el día 7')[1]
        mf=count_pct(sub,'media_fiesta_preferencia','Sí, me parece una buena propuesta')[1]
        rows.append({
            'Comparsa':comp,'N':len(sub),
            'Valoración':round(avg,2) if not pd.isna(avg) else np.nan,
            'Δ valoración vs total':round(avg-global_avg,2) if not pd.isna(avg) and not pd.isna(global_avg) else np.nan,
            'Apoyo día 7 %':round(p7,1),'Δ día 7 vs total':round(p7-global_p7,1),
            'Media Fiesta %':round(mf,1),'Δ Media Fiesta vs total':round(mf-global_mf,1),
        })
    return pd.DataFrame(rows)


def render_simple_summary(df: pd.DataFrame, invited: dict[str, int] | None = None) -> None:
    s=simple_summary_data(df, invited)
    st.markdown('<div class="exec-hero"><div class="eyebrow">Resumen · Junta Directiva</div><div class="headline">Lo importante para decidir en 2–3 minutos</div><div class="subline">Primero la lectura sencilla. Después, si hace falta, puede abrir el análisis detallado para justificar cada conclusión.</div></div>', unsafe_allow_html=True)
    if df.empty:
        st.info("Todavía no hay respuestas. Este resumen se rellenará automáticamente con las encuestas reales.")
        return
    avg=s['avg']
    if avg is None:
        situation='SIN DATOS'; sit_color='#667085'; sit_bg='#f2f4f7'
    elif avg>=4.0:
        situation='POSITIVA'; sit_color='#2f7d32'; sit_bg='#eaf6eb'
    elif avg>=3.4:
        situation='A ESTUDIAR'; sit_color='#b26a00'; sit_bg='#fff4df'
    else:
        situation='REQUIERE REVISIÓN'; sit_color='#b42318'; sit_bg='#fdeceb'
    part_val = "—" if s["participation"] is None else f'{s["participation"]:.1f}%'
    avg_val = "—" if s["avg"] is None else f'{s["avg"]:.2f}/5'
    rec_val = "—" if s["rec"] is None else f'{s["rec"]:.1f}/10'
    k=st.columns(5)
    render_kpi(k[0],"Respuestas",str(s['n']),"Encuestas activas","👥","#981b2b","#f9e7ea")
    render_kpi(k[1],"Participación",part_val,(f"{s['n']} de {s['total_invited']} comparsistas" if s['total_invited'] else "Solo total o comparsa"),"▥","#d19a20","#fbf2dd")
    render_kpi(k[2],"Satisfacción",avg_val,"Valoración general","★","#4c922d","#eaf4e5")
    render_kpi(k[3],"Recomendación",rec_val,"Media 0–10","👍","#2169b4","#e7f0fb")
    render_kpi(k[4],"Comparsas activas",f"{df['comparsa'].nunique()} / 8","Con respuestas","♟","#74459a","#f0e9f6")
    st.write("")
    left,right=st.columns([3.2,1.25])
    with left:
        st.markdown(f'<div class="panel-box"><div class="panel-box-title">Situación general</div><div style="font-size:2rem;font-weight:900;color:{sit_color};background:{sit_bg};padding:14px 16px;border-radius:12px;margin:10px 0">{situation}</div><div class="panel-box-sub">Lectura automática basada en satisfacción, decisiones y señales de mejora.</div></div>',unsafe_allow_html=True)
        rings=st.columns(4)
        satisfaction=(s['avg']/5*100) if s['avg'] is not None else None
        pu_n,pu_pct,_=s['pulsera']; p7_n,p7_pct,_=s['p7']; mf_n,mf_pct,_=s['media']
        render_ring(rings[0],"Satisfacción",satisfaction,f"{avg_val}","#377e2d")
        render_ring(rings[1],"Uso pulsera",pu_pct,f"{pu_n} personas","#754b98")
        render_ring(rings[2],"Apoyo día 7",p7_pct,f"{p7_n} personas","#ed8b00")
        render_ring(rings[3],"Media Fiesta 2 días",mf_pct,f"{mf_n} personas","#168d7a")
    with right:
        st.markdown('<div class="panel-box"><div class="panel-box-title">Semáforo de decisiones</div><div class="panel-box-sub">Prioridades detectadas</div>',unsafe_allow_html=True)
        st.markdown(f'<div class="result-pill"><span class="answer">🟢 Mantener</span><span class="number">{len(s["green"])}</span></div>',unsafe_allow_html=True)
        st.markdown(f'<div class="result-pill"><span class="answer">🟠 Estudiar</span><span class="number">{len(s["amber"])}</span></div>',unsafe_allow_html=True)
        st.markdown(f'<div class="result-pill"><span class="answer">🔴 Revisar</span><span class="number">{len(s["red"])}</span></div>',unsafe_allow_html=True)
        st.markdown('</div>',unsafe_allow_html=True)
    st.markdown("### Lo que funciona · decisiones · alertas")
    c1,c2,c3=st.columns(3)
    with c1:
        body=''.join(f'<div class="t-item">• {x}</div>' for x in s['green']) if s['green'] else '<div class="t-item">Todavía no hay señales claras.</div>'
        st.markdown('<div class="traffic green"><div class="t-title">🟢 LO QUE FUNCIONA</div>'+body+'</div>', unsafe_allow_html=True)
    with c2:
        body=''.join(f'<div class="t-item">• {x}</div>' for x in s['decisions']) if s['decisions'] else '<div class="t-item">Sin decisiones claras todavía.</div>'
        st.markdown('<div class="traffic amber"><div class="t-title">⚖️ DECISIONES A TOMAR</div>'+body+'</div>', unsafe_allow_html=True)
    with c3:
        body=''.join(f'<div class="t-item">• {x}</div>' for x in (s['red']+s['amber'])[:6]) if (s['red'] or s['amber']) else '<div class="t-item">No aparece ninguna alerta prioritaria.</div>'
        st.markdown('<div class="traffic red"><div class="t-title">🔴 ALERTAS / A REVISAR</div>'+body+'</div>', unsafe_allow_html=True)
    d=decision_rows(df)
    if not d.empty:
        st.markdown("### Decisiones en cifras")
        for tema in d['Tema'].drop_duplicates():
            sub=d[d['Tema']==tema]
            st.markdown(f"**{tema}**")
            cols=st.columns(len(sub))
            for col,(_,r) in zip(cols,sub.iterrows()):
                col.metric(r['Opción'],f"{int(r['Personas'])} personas",f"{r['Porcentaje']:.1f}%")
    st.caption("Para profundizar, utiliza ‘Decisiones clave’, ‘Análisis detallado’, ‘Comparsas’ y los informes descargables.")


# =============================================================
# INFORMES PDF V18 · DISEÑO INSTITUCIONAL
# =============================================================

PDF_BURGUNDY = colors.HexColor("#7A1720")
PDF_BURGUNDY_DARK = colors.HexColor("#561017")
PDF_GOLD = colors.HexColor("#C69B3C")
PDF_NAVY = colors.HexColor("#17324D")
PDF_GREEN = colors.HexColor("#3F8A3A")
PDF_ORANGE = colors.HexColor("#D98215")
PDF_RED = colors.HexColor("#B42318")
PDF_PURPLE = colors.HexColor("#67428A")
PDF_CREAM = colors.HexColor("#FBF8F1")
PDF_SOFT = colors.HexColor("#F5F6F8")
PDF_BORDER = colors.HexColor("#DDD7CC")
PDF_TEXT = colors.HexColor("#182230")
PDF_MUTED = colors.HexColor("#667085")


def _pdf_safe(value: Any) -> str:
    """Texto seguro para las fuentes estándar de ReportLab."""
    text = str(value if value is not None else "")
    return (text.replace("–", "-").replace("—", "-").replace("·", " | ")
                .replace("“", '"').replace("”", '"').replace("’", "'"))


def _pdf_logo_file() -> str | None:
    path = Path(LOGO_PATH)
    return str(path) if path.exists() else None


def _pdf_background_file() -> str | None:
    path = Path(COMPARSAS_BG_PATH)
    return str(path) if path.exists() else None


def _pdf_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_org": ParagraphStyle("cover_org_v18", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=PDF_BURGUNDY, alignment=TA_CENTER, spaceAfter=2*mm),
        "cover_title": ParagraphStyle("cover_title_v18", parent=base["Title"], fontName="Times-Bold", fontSize=23, leading=28, textColor=PDF_NAVY, alignment=TA_CENTER, spaceAfter=4*mm),
        "cover_sub": ParagraphStyle("cover_sub_v18", parent=base["Normal"], fontName="Helvetica", fontSize=10.5, leading=15, textColor=PDF_MUTED, alignment=TA_CENTER),
        "h1": ParagraphStyle("h1_v18", parent=base["Heading1"], fontName="Times-Bold", fontSize=18, leading=22, textColor=PDF_NAVY, spaceBefore=2*mm, spaceAfter=3*mm),
        "h2": ParagraphStyle("h2_v18", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=PDF_BURGUNDY, spaceBefore=3*mm, spaceAfter=2*mm),
        "body": ParagraphStyle("body_v18", parent=base["BodyText"], fontName="Helvetica", fontSize=8.6, leading=12, textColor=PDF_TEXT),
        "body_small": ParagraphStyle("body_small_v18", parent=base["BodyText"], fontName="Helvetica", fontSize=7.7, leading=10.5, textColor=PDF_TEXT),
        "muted": ParagraphStyle("muted_v18", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=PDF_MUTED),
        "card_label": ParagraphStyle("card_label_v18", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.2, leading=9, textColor=PDF_MUTED, alignment=TA_CENTER),
        "card_value": ParagraphStyle("card_value_v18", parent=base["Normal"], fontName="Times-Bold", fontSize=17, leading=19, textColor=PDF_NAVY, alignment=TA_CENTER),
        "card_note": ParagraphStyle("card_note_v18", parent=base["Normal"], fontName="Helvetica", fontSize=6.8, leading=9, textColor=PDF_MUTED, alignment=TA_CENTER),
        "white_small": ParagraphStyle("white_small_v18", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.4, leading=9, textColor=colors.white),
        "table": ParagraphStyle("table_v18", parent=base["Normal"], fontName="Helvetica", fontSize=7.2, leading=9, textColor=PDF_TEXT),
        "table_bold": ParagraphStyle("table_bold_v18", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.2, leading=9, textColor=PDF_TEXT),
        "quote": ParagraphStyle("quote_v18", parent=base["BodyText"], fontName="Times-Italic", fontSize=9.2, leading=13, textColor=PDF_NAVY, leftIndent=3*mm, rightIndent=3*mm),
    }


def _pdf_cover_canvas(canvas, doc) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(PDF_CREAM)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    bg = _pdf_background_file()
    if bg:
        try:
            canvas.drawImage(bg, 0, 0, width=width, height=height, preserveAspectRatio=False, mask='auto')
        except Exception:
            pass
    # Banda inferior institucional.
    canvas.setFillColor(PDF_BURGUNDY_DARK)
    canvas.rect(0, 0, width, 49*mm, fill=1, stroke=0)
    canvas.setFillColor(PDF_GOLD)
    canvas.rect(0, 49*mm, width, 1.2*mm, fill=1, stroke=0)
    # Filetes superiores.
    canvas.setStrokeColor(PDF_GOLD)
    canvas.setLineWidth(0.7)
    canvas.line(20*mm, height-18*mm, width-20*mm, height-18*mm)
    canvas.restoreState()


def _pdf_page_canvas(canvas, doc) -> None:
    width, height = A4
    canvas.saveState()
    # Cabecera.
    canvas.setStrokeColor(PDF_GOLD)
    canvas.setLineWidth(0.55)
    canvas.line(16*mm, height-18*mm, width-16*mm, height-18*mm)
    logo = _pdf_logo_file()
    if logo:
        try:
            canvas.drawImage(logo, 16*mm, height-15.2*mm, width=9*mm, height=9*mm, preserveAspectRatio=True, anchor='c', mask='auto')
        except Exception:
            pass
    canvas.setFillColor(PDF_NAVY)
    canvas.setFont("Helvetica-Bold", 8.2)
    canvas.drawString(28*mm, height-11.4*mm, "ENCUESTA MOROS Y CRISTIANOS DE ASPE 2026")
    canvas.setFillColor(PDF_BURGUNDY)
    canvas.setFont("Helvetica-Bold", 6.7)
    canvas.drawString(28*mm, height-15*mm, "INFORME DE RESULTADOS | JUNTA CENTRAL")
    # Página.
    canvas.setFillColor(PDF_BURGUNDY)
    canvas.roundRect(width-40*mm, height-15.8*mm, 24*mm, 7*mm, 2*mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 6.8)
    canvas.drawCentredString(width-28*mm, height-13.3*mm, f"PÁGINA {doc.page-1}")
    # Pie.
    canvas.setStrokeColor(PDF_BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(16*mm, 12.5*mm, width-16*mm, 12.5*mm)
    canvas.setFillColor(PDF_MUTED)
    canvas.setFont("Helvetica", 6.3)
    canvas.drawString(16*mm, 8.5*mm, "Unión de Moros y Cristianos Virgen de las Nieves | Aspe")
    canvas.drawRightString(width-16*mm, 8.5*mm, "Documento generado automáticamente por el panel de resultados")
    canvas.restoreState()


def _pdf_cover_story(scope_name: str, n: int, report_kind: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    story: list[Any] = [Spacer(1, 28*mm)]
    logo = _pdf_logo_file()
    if logo:
        story += [Image(logo, width=42*mm, height=42*mm), Spacer(1, 4*mm)]
    story += [
        Paragraph("JUNTA CENTRAL", styles["cover_org"]),
        Paragraph("UNIÓN DE MOROS Y CRISTIANOS VIRGEN DE LAS NIEVES - ASPE", styles["cover_org"]),
        Spacer(1, 10*mm),
        Paragraph("INFORME DE RESULTADOS", styles["cover_title"]),
        Paragraph("ENCUESTA MOROS Y CRISTIANOS<br/>DE ASPE 2026", styles["cover_title"]),
        HRFlowable(width="64%", thickness=0.8, color=PDF_GOLD, spaceBefore=2*mm, spaceAfter=5*mm),
        Paragraph(_pdf_safe(report_kind), styles["cover_sub"]),
        Paragraph(f"Ámbito analizado: <b>{_pdf_safe(scope_name)}</b>", styles["cover_sub"]),
        Paragraph(f"Respuestas analizadas: <b>{n}</b>", styles["cover_sub"]),
        Spacer(1, 39*mm),
        Paragraph("Tu opinión nos ayuda a mejorar nuestras fiestas", ParagraphStyle("cover_phrase_v18", parent=styles["cover_sub"], fontName="Times-Italic", fontSize=11.5, textColor=PDF_GOLD)),
        Spacer(1, 26*mm),
        Paragraph(f"INFORME GENERADO EL {datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle("cover_date_v18", parent=styles["cover_sub"], fontName="Helvetica-Bold", fontSize=8.5, textColor=colors.white)),
        PageBreak(),
    ]
    return story


def _pdf_section_title(title: str, styles: dict[str, ParagraphStyle], subtitle: str | None = None) -> list[Any]:
    items: list[Any] = [Paragraph(_pdf_safe(title), styles["h1"]), HRFlowable(width="100%", thickness=0.7, color=PDF_GOLD, spaceAfter=3*mm)]
    if subtitle:
        items += [Paragraph(_pdf_safe(subtitle), styles["muted"]), Spacer(1, 2*mm)]
    return items


def _pdf_kpi_cards(s: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    part = "-" if s["participation"] is None else f'{s["participation"]:.1f}%'
    avg = "-" if s["avg"] is None else f'{s["avg"]:.2f} / 5'
    rec = "-" if s["rec"] is None else f'{s["rec"]:.1f} / 10'
    invited_note = f'{s["n"]} de {s["total_invited"]} comparsistas' if s["total_invited"] else "Participación no calculable"
    cards = [
        ("RESPUESTAS", str(s["n"]), "Encuestas analizadas", PDF_BURGUNDY),
        ("PARTICIPACIÓN", part, invited_note, PDF_GOLD),
        ("VALORACIÓN GENERAL", avg, "Satisfacción media", PDF_GREEN),
        ("RECOMENDACIÓN", rec, "Escala de 0 a 10", PDF_NAVY),
    ]
    cells=[]
    for label,value,note,color in cards:
        inner=Table([
            [Paragraph(label, styles["card_label"])],
            [Paragraph(value, styles["card_value"])],
            [Paragraph(_pdf_safe(note), styles["card_note"])],
        ], colWidths=[41*mm], rowHeights=[8*mm,13*mm,10*mm])
        inner.setStyle(TableStyle([
            ('BOX',(0,0),(-1,-1),0.6,PDF_BORDER),('BACKGROUND',(0,0),(-1,-1),colors.white),
            ('LINEABOVE',(0,0),(-1,0),3,color),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),3*mm),('RIGHTPADDING',(0,0),(-1,-1),3*mm),
        ]))
        cells.append(inner)
    table=Table([cells], colWidths=[43.5*mm]*4, hAlign='CENTER')
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1.2*mm),('RIGHTPADDING',(0,0),(-1,-1),1.2*mm)]))
    return table


def _pdf_decision_table(df: pd.DataFrame, styles: dict[str, ParagraphStyle]) -> Table | None:
    data=decision_rows(df)
    if data.empty:
        return None
    rows=[[Paragraph("TEMA",styles["white_small"]),Paragraph("OPCIÓN",styles["white_small"]),Paragraph("PERSONAS",styles["white_small"]),Paragraph("%",styles["white_small"])]]
    for topic in data["Tema"].drop_duplicates():
        sub=data[data["Tema"]==topic].sort_values("Porcentaje",ascending=False)
        first=True
        for _,r in sub.iterrows():
            rows.append([
                Paragraph(_pdf_safe(topic) if first else "", styles["table_bold"]),
                Paragraph(_pdf_safe(r["Opción"]), styles["table"]),
                Paragraph(str(int(r["Personas"])), styles["table"]),
                Paragraph(f'{r["Porcentaje"]:.1f}%', styles["table_bold"]),
            ])
            first=False
    t=Table(rows,colWidths=[55*mm,68*mm,25*mm,25*mm],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),PDF_BURGUNDY),('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('GRID',(0,0),(-1,-1),0.35,PDF_BORDER),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PDF_SOFT]),
        ('TOPPADDING',(0,0),(-1,-1),4.5),('BOTTOMPADDING',(0,0),(-1,-1),4.5),
    ]))
    return t


def _pdf_status_boxes(s: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    sections=[
        ("MANTENER", s.get("green") or ["Sin aspectos destacados todavía."], PDF_GREEN),
        ("ESTUDIAR", s.get("amber") or ["Sin aspectos destacados todavía."], PDF_ORANGE),
        ("REVISAR", s.get("red") or ["Sin alertas prioritarias con los datos actuales."], PDF_RED),
    ]
    cells=[]
    for title,items,color in sections:
        body=[Paragraph(title, ParagraphStyle(f"box_{title}", parent=styles["table_bold"], fontSize=8.2, textColor=color, spaceAfter=2*mm))]
        for item in items[:4]:
            body.append(Paragraph("&bull; "+_pdf_safe(item), styles["body_small"]))
            body.append(Spacer(1,1*mm))
        inner=Table([[body]],colWidths=[54*mm])
        inner.setStyle(TableStyle([
            ('BOX',(0,0),(-1,-1),0.65,PDF_BORDER),('BACKGROUND',(0,0),(-1,-1),colors.white),
            ('LINEABOVE',(0,0),(-1,0),3,color),('LEFTPADDING',(0,0),(-1,-1),4*mm),('RIGHTPADDING',(0,0),(-1,-1),4*mm),('TOPPADDING',(0,0),(-1,-1),4*mm),('BOTTOMPADDING',(0,0),(-1,-1),4*mm),
        ]))
        cells.append(inner)
    outer=Table([cells],colWidths=[57*mm]*3,hAlign='CENTER')
    outer.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1.2*mm),('RIGHTPADDING',(0,0),(-1,-1),1.2*mm)]))
    return outer


def _pdf_acts_table(df: pd.DataFrame, styles: dict[str, ParagraphStyle], limit: int | None = None) -> Table:
    acts=acts_summary(df).sort_values("Valoración media",ascending=False,na_position='last')
    if limit:
        acts=acts.head(limit)
    rows=[[Paragraph("ACTO",styles["white_small"]),Paragraph("MEDIA",styles["white_small"]),Paragraph("N",styles["white_small"]),Paragraph("4-5",styles["white_small"])]]
    for _,r in acts.iterrows():
        avg="-" if pd.isna(r["Valoración media"]) else f'{r["Valoración media"]:.2f}'
        high="-" if pd.isna(r["Valoraciones 4-5 %"]) else f'{r["Valoraciones 4-5 %"]:.1f}%'
        rows.append([Paragraph(_pdf_safe(r["Acto"]),styles["table"]),Paragraph(avg,styles["table_bold"]),Paragraph(str(int(r["Respuestas que valoran"])),styles["table"]),Paragraph(high,styles["table"])] )
    t=Table(rows,colWidths=[112*mm,22*mm,18*mm,22*mm],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),PDF_NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.3,PDF_BORDER),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PDF_SOFT]),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),4.2),('BOTTOMPADDING',(0,0),(-1,-1),4.2),
    ]))
    return t


def _pdf_comparsa_table(df: pd.DataFrame, invited: dict[str, int], styles: dict[str, ParagraphStyle]) -> Table:
    global_avg=pd.to_numeric(df.get("valoracion_general",pd.Series(dtype=float)),errors='coerce').mean()
    rows=[[Paragraph("COMPARSA",styles["white_small"]),Paragraph("COMPARSISTAS",styles["white_small"]),Paragraph("RESP.",styles["white_small"]),Paragraph("PARTIC.",styles["white_small"]),Paragraph("VALORACIÓN",styles["white_small"]),Paragraph("VS TOTAL",styles["white_small"])]]
    for comp in COMPARSAS:
        sub=df[df.get("comparsa")==comp] if "comparsa" in df.columns else pd.DataFrame()
        n=len(sub); total=int(invited.get(comp,0) or 0)
        part=f"{(n/total*100):.1f}%" if total else "-"
        avg=pd.to_numeric(sub.get("valoracion_general",pd.Series(dtype=float)),errors='coerce').mean() if n else np.nan
        delta=(avg-global_avg) if n and not pd.isna(avg) and not pd.isna(global_avg) else np.nan
        delta_text="-" if pd.isna(delta) else f'{delta:+.2f}'
        rows.append([
            Paragraph(_pdf_safe(comp),styles["table"]),Paragraph(str(total) if total else "-",styles["table"]),Paragraph(str(n),styles["table_bold"]),Paragraph(part,styles["table"]),
            Paragraph("-" if pd.isna(avg) else f'{avg:.2f}/5',styles["table_bold"]),Paragraph(delta_text,styles["table"])
        ])
    t=Table(rows,colWidths=[66*mm,27*mm,18*mm,24*mm,25*mm,20*mm],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),PDF_BURGUNDY),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.3,PDF_BORDER),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PDF_SOFT]),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
    ]))
    return t


def _pdf_theme_table(themes: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table | None:
    if not themes:
        return None
    rows=[[Paragraph("TEMA",styles["white_small"]),Paragraph("MENCIONES",styles["white_small"]),Paragraph("% COMENTARIOS",styles["white_small"])]]
    for x in themes:
        rows.append([Paragraph(_pdf_safe(x.get("Tema","")),styles["table"]),Paragraph(str(x.get("Menciones",0)),styles["table_bold"]),Paragraph(f'{float(x.get("% comentarios",0)):.1f}%',styles["table"] )])
    t=Table(rows,colWidths=[100*mm,35*mm,40*mm],repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),PDF_PURPLE),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.3,PDF_BORDER),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PDF_SOFT]),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
    ]))
    return t


def _build_pdf_document(story: list[Any], out: io.BytesIO) -> bytes:
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=24*mm,bottomMargin=17*mm,title="Informe de resultados - Encuesta Moros y Cristianos Aspe 2026",author="Junta Central - Unión de Moros y Cristianos Virgen de las Nieves")
    doc.build(story,onFirstPage=_pdf_cover_canvas,onLaterPages=_pdf_page_canvas)
    return out.getvalue()


def simple_report_pdf_bytes(df: pd.DataFrame, scope_name: str, invited: dict[str, int]) -> bytes:
    """Informe visual y breve para una reunión de Junta."""
    out=io.BytesIO(); styles=_pdf_styles(); s=simple_summary_data(df,invited,False)
    story=_pdf_cover_story(scope_name,len(df),"INFORME RESUMIDO | Lectura rápida para la Junta",styles)
    story += _pdf_section_title("RESUMEN",styles,"Las cifras esenciales y una lectura sencilla de los resultados.")
    if df.empty:
        story += [Paragraph("Todavía no hay respuestas disponibles.",styles["body"])]
        return _build_pdf_document(story,out)
    story += [_pdf_kpi_cards(s,styles),Spacer(1,5*mm)]
    # Lectura principal destacada.
    lead=s["key_messages"][:5] or ["No hay datos suficientes para generar una lectura automática."]
    lead_text="<br/>".join("&bull; "+_pdf_safe(x) for x in lead)
    box=Table([[Paragraph(lead_text,styles["body"])]],colWidths=[174*mm])
    box.setStyle(TableStyle([('BOX',(0,0),(-1,-1),0.7,PDF_BORDER),('BACKGROUND',(0,0),(-1,-1),PDF_CREAM),('LINEBEFORE',(0,0),(0,-1),4,PDF_GOLD),('LEFTPADDING',(0,0),(-1,-1),5*mm),('RIGHTPADDING',(0,0),(-1,-1),5*mm),('TOPPADDING',(0,0),(-1,-1),4*mm),('BOTTOMPADDING',(0,0),(-1,-1),4*mm)]))
    story += [Paragraph("LECTURA RÁPIDA",styles["h2"]),box,Spacer(1,4*mm),_pdf_status_boxes(s,styles),PageBreak()]

    story += _pdf_section_title("DECISIONES CLAVE",styles,"Número de personas y porcentaje para las cuestiones que pueden implicar una decisión.")
    dt=_pdf_decision_table(df,styles)
    if dt: story += [dt,Spacer(1,5*mm)]
    story += [Paragraph("QUÉ CONVIENE LLEVAR A LA JUNTA",styles["h2"])]
    for x in s.get("decisions",[]): story += [Paragraph("&bull; "+_pdf_safe(x),styles["body"]),Spacer(1,1.4*mm)]
    story += [Spacer(1,3*mm),Paragraph("ACTOS MEJOR VALORADOS",styles["h2"]),_pdf_acts_table(df,styles,limit=5),PageBreak()]

    exec_data=executive_interpretation(df,invited,False)
    story += _pdf_section_title("CONCLUSIONES",styles,"Una síntesis para cerrar la reunión sin necesidad de revisar todas las estadísticas.")
    for heading,key,color in [("FORTALEZAS A MANTENER","strengths",PDF_GREEN),("ASPECTOS A REVISAR","watchouts",PDF_ORANGE),("RECOMENDACIONES PARA 2027","actions",PDF_BURGUNDY)]:
        items=exec_data.get(key) or ["Sin elementos destacados con los datos actuales."]
        content=[Paragraph(heading,ParagraphStyle(f"easy_{key}_v18",parent=styles["h2"],textColor=color))]
        for item in items[:5]: content += [Paragraph("&bull; "+_pdf_safe(item),styles["body"]),Spacer(1,1.2*mm)]
        panel=Table([[content]],colWidths=[174*mm])
        panel.setStyle(TableStyle([('BOX',(0,0),(-1,-1),0.55,PDF_BORDER),('BACKGROUND',(0,0),(-1,-1),colors.white),('LINEBEFORE',(0,0),(0,-1),4,color),('LEFTPADDING',(0,0),(-1,-1),5*mm),('RIGHTPADDING',(0,0),(-1,-1),5*mm),('TOPPADDING',(0,0),(-1,-1),3*mm),('BOTTOMPADDING',(0,0),(-1,-1),3*mm)]))
        story += [panel,Spacer(1,3*mm)]
    theme_table=_pdf_theme_table(exec_data.get("themes",[]),styles)
    if theme_table:
        story += [Paragraph("TEMAS RECURRENTES EN COMENTARIOS",styles["h2"]),theme_table,Spacer(1,3*mm)]
    story += [Spacer(1,3*mm),Paragraph("Este informe está pensado para una lectura rápida. Para justificar una decisión con todo el detalle, utilice el Informe completo y el panel de la Junta.",styles["muted"])]
    return _build_pdf_document(story,out)


def report_pdf_bytes(df: pd.DataFrame, scope_name: str, invited: dict[str, int]) -> bytes:
    """Informe institucional completo, con detalle para archivo y análisis."""
    out=io.BytesIO(); styles=_pdf_styles(); s=simple_summary_data(df,invited,False); exec_data=executive_interpretation(df,invited,False)
    story=_pdf_cover_story(scope_name,len(df),"INFORME COMPLETO | Resultados, comparsas, actos y conclusiones",styles)
    story += _pdf_section_title("RESUMEN",styles,"Vista general del ámbito seleccionado.")
    if df.empty:
        story += [Paragraph("Todavía no hay respuestas disponibles.",styles["body"])]
        return _build_pdf_document(story,out)
    story += [_pdf_kpi_cards(s,styles),Spacer(1,5*mm)]
    story += [Paragraph(_pdf_safe(exec_data.get("headline","")),ParagraphStyle("headline_pdf_v18",parent=styles["quote"],fontName="Times-Bold",fontSize=11,textColor=PDF_BURGUNDY)),Spacer(1,2*mm),Paragraph(_pdf_safe(exec_data.get("subline","")),styles["muted"]),Spacer(1,4*mm),_pdf_status_boxes(s,styles),PageBreak()]

    # Decisiones.
    story += _pdf_section_title("DECISIONES CLAVE",styles,"Las preguntas con mayor utilidad para tomar decisiones organizativas.")
    dt=_pdf_decision_table(df,styles)
    if dt: story += [dt,Spacer(1,5*mm)]
    for x in s.get("decisions",[]): story += [Paragraph("&bull; "+_pdf_safe(x),styles["body"]),Spacer(1,1.2*mm)]
    story += [PageBreak()]

    # Actos.
    story += _pdf_section_title("VALORACIÓN DE ACTOS",styles,"Media de 1 a 5. Las respuestas 'No asistí / No puedo valorarlo' no se incluyen en la media.")
    story += [_pdf_acts_table(df,styles),Spacer(1,4*mm)]
    rank=ranking_summary(df)
    if not rank.empty:
        story += [Paragraph("RANKING DE LOS 3 ACTOS FAVORITOS",styles["h2"])]
        rr=[[Paragraph("ACTO",styles["white_small"]),Paragraph("VECES ELEGIDO",styles["white_small"]),Paragraph("PUNTOS",styles["white_small"]),Paragraph("VECES FAVORITO",styles["white_small"])]]
        for _,r in rank.head(10).iterrows():
            rr.append([Paragraph(_pdf_safe(r["Acto"]),styles["table"]),Paragraph(str(int(r["Veces elegido"])),styles["table"]),Paragraph(str(int(r["Puntuación total"])),styles["table_bold"]),Paragraph(str(int(r["Veces como favorito"])),styles["table"] )])
        rt=Table(rr,colWidths=[98*mm,28*mm,24*mm,28*mm],repeatRows=1)
        rt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PDF_GOLD),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.3,PDF_BORDER),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PDF_SOFT]),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story += [rt]
    story += [PageBreak()]

    # Comparsas.
    story += _pdf_section_title("RESULTADOS POR COMPARSAS",styles,"Participación y valoración para detectar diferencias frente al resultado total.")
    story += [_pdf_comparsa_table(df,invited,styles),Spacer(1,4*mm),Paragraph("La columna 'VS TOTAL' compara la valoración media de cada comparsa con la media del ámbito analizado. Un valor positivo está por encima del total y uno negativo por debajo.",styles["muted"]),PageBreak()]

    # Interpretación.
    story += _pdf_section_title("INTERPRETACIÓN Y CONCLUSIONES",styles,"Lectura automática de apoyo. Las decisiones finales corresponden a la Junta y deben contrastarse con el número de respuestas.")
    for heading,key,color in [("CONCLUSIONES PRINCIPALES","conclusions",PDF_NAVY),("FORTALEZAS A MANTENER","strengths",PDF_GREEN),("ASPECTOS A REVISAR","watchouts",PDF_ORANGE),("RECOMENDACIONES PARA 2027","actions",PDF_BURGUNDY),("DATOS QUE SUSTENTAN LA LECTURA","evidence",PDF_PURPLE)]:
        story += [Paragraph(heading,ParagraphStyle(f"full_{key}_v18",parent=styles["h2"],textColor=color))]
        items=exec_data.get(key) or ["Sin elementos destacados con los datos actuales."]
        for pt in items:
            story += [Paragraph("&bull; "+_pdf_safe(pt),styles["body"]),Spacer(1,1.1*mm)]
        story += [Spacer(1,2*mm)]
    theme_table=_pdf_theme_table(exec_data.get("themes",[]),styles)
    if theme_table:
        story += [Paragraph("TEMAS RECURRENTES EN COMENTARIOS",styles["h2"]),theme_table,Spacer(1,4*mm)]
    story += [HRFlowable(width="100%",thickness=0.7,color=PDF_GOLD,spaceBefore=4*mm,spaceAfter=3*mm),Paragraph("Nota metodológica: los porcentajes deben leerse junto al número de personas. Cuando se aplican filtros demográficos, no se calcula un porcentaje de participación si no se conoce el número total de comparsistas de ese segmento.",styles["muted"])]
    return _build_pdf_document(story,out)


def report_excel_bytes(df: pd.DataFrame, invited: dict[str, int]) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        export_df = df.drop(columns=["id", "excluded"], errors="ignore").copy()
        export_df.to_excel(writer, sheet_name="Respuestas", index=False)
        acts_summary(df).to_excel(writer, sheet_name="Actos", index=False)
        ranking_summary(df).to_excel(writer, sheet_name="Ranking actos", index=False)
        distributions = []
        distribution_fields = [
            ("evolucion", "Evolución de las fiestas", None),
            ("cantidad_actos", "Cantidad de actos", None),
            ("pulsera_usada", "Uso de pulsera", {True:"Sí", False:"No"}),
            ("pulsera_utilidad", "Utilidad de pulsera", None),
            ("pasacalles_preferencia", "Preferencia Pasacalles", None),
            ("media_fiesta_preferencia", "Media Fiesta 2027", None),
            ("castillo_avenida", "Castillo Festero en Avenida de la Constitución", {
                "Sí, me gustaría que estuviese allí.": "Sí · Avenida de la Constitución",
                "No, prefiero que se mantenga en su ubicación actual.": "No · Ubicación actual",
                "Me es indiferente / No tengo una preferencia clara.": "Indiferente",
            }),
        ]
        for field, question, labels in distribution_fields:
            part = breakdown_counts(df, field, labels)
            if not part.empty:
                part.insert(0, "Pregunta", question)
                distributions.append(part)
        if distributions:
            pd.concat(distributions, ignore_index=True).to_excel(writer, sheet_name="Distribuciones", index=False)
        exec_data = executive_interpretation(df, invited, False)
        executive_rows=[]
        for section_name,key in [("Conclusiones principales","conclusions"),("Fortalezas","strengths"),("Aspectos a revisar","watchouts"),("Recomendaciones 2027","actions"),("Datos de apoyo","evidence")]:
            for item in exec_data[key]: executive_rows.append({"Sección":section_name,"Interpretación":item})
        pd.DataFrame(executive_rows).to_excel(writer, sheet_name="Interpretacion", index=False)
        if exec_data["themes"]:
            pd.DataFrame(exec_data["themes"]).to_excel(writer, sheet_name="Temas comentarios", index=False)
    return out.getvalue()


def top_filters(df: pd.DataFrame) -> pd.DataFrame:
    cols = st.columns([1.25,1.2,1.25,1.45,.72])
    selections = {}
    with cols[0]: selections["comparsa"] = st.selectbox("COMPARSA", ["Todas"] + COMPARSAS, key="top_comparsa")
    with cols[1]: selections["edad"] = st.selectbox("EDAD", ["Todas"] + EDADES, key="top_edad")
    with cols[2]: selections["antiguedad"] = st.selectbox("ANTIGÜEDAD FESTERA", ["Todas"] + ANTIGUEDADES, key="top_antiguedad")
    with cols[3]: selections["cargo"] = st.selectbox("CARGO / RESPONSABILIDAD", ["Todos"] + CARGOS, key="top_cargo")
    with cols[4]:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button("↻ Limpiar", use_container_width=True, key="clear_top_filters"):
            for key in ["top_comparsa","top_edad","top_antiguedad","top_cargo"]:
                st.session_state.pop(key, None)
            st.rerun()
    out = df.copy()
    for col, val in selections.items():
        if val not in ["Todas", "Todos"]:
            out = out[out[col] == val]
    return out

def render_admin() -> None:
    if not admin_authenticated():
        render_admin_login()
        return

    st.markdown('<style>.stApp{background:#f6f8fb!important;} .block-container{max-width:1500px!important;padding-top:1.1rem!important;}</style>', unsafe_allow_html=True)

    menu = {
        "⭐ Resumen": "Resumen",
        "⚖️ Decisiones clave": "Decisiones clave",
        "📊 Análisis detallado": "Resumen general",
        "👥 Comparsas": "Comparsas",
        "📅 Actos": "Actos",
        "◉ Pulsera festera": "Pulsera festera",
        "⚑ Pasacalles festero": "Pasacalles festero",
        "✦ Media Fiesta 2027": "Media Fiesta 2027",
        "🏰 Castillo Festero": "Castillo Festero",
        "💬 Comentarios": "Comentarios",
        "⇩ Informes": "Informes",
        "⚙️ Administración": "Gestionar encuestas",
        "ⓘ Cómo interpretar": "Cómo interpretar",
    }
    # Navegación del panel de Junta:
    # sidebar izquierdo abierto por defecto, plegable y con control de reapertura visible.
    menu_labels = list(menu.keys())
    st.session_state.setdefault("admin_sidebar_nav", menu_labels[0])

    # IMPORTANTE:
    # En la encuesta pública se mantienen ocultos los controles de Streamlit,
    # pero en el área admin se restaura la cabecera mínima necesaria para que
    # Streamlit muestre siempre el botón nativo de plegar/desplegar el sidebar.
    st.markdown(
        """
        <style>
        /* Barra lateral visible cuando está expandida */
        section[data-testid="stSidebar"],
        [data-testid="stSidebar"] {
            visibility: visible !important;
            opacity: 1 !important;
        }

        /* Restaurar la cabecera SOLO dentro del panel admin */
        header[data-testid="stHeader"],
        [data-testid="stHeader"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            height: 3.25rem !important;
            min-height: 3.25rem !important;
            background: transparent !important;
            pointer-events: auto !important;
        }

        /* Control nativo para volver a abrir el sidebar */
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapseButton"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 999999 !important;
        }

        /* Algunos builds recientes de Streamlit colocan el control en la toolbar.
           La restauramos en admin, pero ocultamos los elementos de despliegue. */
        [data-testid="stToolbar"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }
        [data-testid="stAppDeployButton"],
        [data-testid="manage-app-button"],
        [data-testid="stViewerBadge"] {
            display: none !important;
        }

        /* Botones de cabecera / colapso */
        button[kind="header"],
        button[data-testid="stSidebarCollapsedControl"],
        button[data-testid="stSidebarCollapseButton"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }

        /* En escritorio, reservar correctamente el ancho del sidebar. */
        @media (min-width: 769px) {
            section[data-testid="stSidebar"][aria-expanded="true"],
            [data-testid="stSidebar"][aria-expanded="true"] {
                min-width: 19rem !important;
                width: 19rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.image(LOGO_PATH, width=125)
        st.markdown("### UNIÓN DE MOROS Y CRISTIANOS\n**VIRGEN DE LAS NIEVES · ASPE**")
        selected_menu = st.radio(
            "",
            menu_labels,
            key="admin_sidebar_nav",
            label_visibility="collapsed",
        )
        section = menu[selected_menu]
        st.markdown("---")
        if st.button("Cerrar sesión", use_container_width=True):
            for k in ["admin_authenticated","admin_user","admin_password","admin_sidebar_nav"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.caption("Encuesta Fiestas de Moros y Cristianos de Aspe 2026")

    all_df = fetch_all_responses()
    if not all_df.empty and "excluded" not in all_df.columns:
        all_df["excluded"] = False
    df = all_df[~all_df.get("excluded", False).fillna(False).astype(bool)].copy() if not all_df.empty else all_df.copy()
    now_text = f"{datetime.now():%d/%m/%Y · %H:%M}"
    st.markdown(f'''<div class="admin-topbar"><div><div class="dashboard-title">{section.upper()}</div><div class="dashboard-sub">Encuesta Fiestas de Moros y Cristianos de Aspe 2026</div></div><div class="admin-updated">Última actualización:<br><b>{now_text}</b><br><span class="live-badge"><span class="live-dot"></span> Datos actualizados</span></div></div>''', unsafe_allow_html=True)

    invited = get_invited_counts()
    total_invited = sum(invited.values())

    if df.empty and section != "Gestionar encuestas":
        excluded_n = int(all_df.get("excluded", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()) if not all_df.empty else 0
        st.warning("Todavía no hay respuestas activas para analizar. El panel se completará automáticamente cuando comiencen a responder los festeros.")
        # Incluso con 0 respuestas, la Junta debe ver desde el primer momento
        # el universo real de comparsistas utilizado para calcular participación.
        c1, c2, c3 = st.columns(3)
        render_kpi(c1, "Respuestas recibidas", "0", "La encuesta empieza desde cero", "👥", "#981b2b", "#f9e7ea")
        render_kpi(c2, "Comparsistas", f"{total_invited:,}".replace(",", "."), "Total de las 8 comparsas", "♟", "#74459a", "#f0e9f6")
        render_kpi(c3, "Participación", "0,0%", f"0 de {total_invited} comparsistas", "▥", "#d19a20", "#fbf2dd")
        st.markdown("### Comparsistas por comparsa")
        zero_rows = [{"Comparsa": comp, "Comparsistas": int(invited.get(comp, 0)), "Respuestas": 0, "Participación": "0,0%"} for comp in COMPARSAS]
        st.dataframe(pd.DataFrame(zero_rows), use_container_width=True, hide_index=True)
        if excluded_n:
            st.info(f"Hay {excluded_n} encuesta(s) excluida(s) temporalmente. Puedes recuperarlas desde Administración.")
        return

    filtered = top_filters(df) if not df.empty else df.copy()
    n = len(filtered)
    avg = pd.to_numeric(filtered.get("valoracion_general", pd.Series(dtype=float)), errors="coerce").mean()
    rec = pd.to_numeric(filtered.get("recomendacion", pd.Series(dtype=float)), errors="coerce").mean()
    selected_comp = st.session_state.get("top_comparsa", "Todas")
    demographic_filter_active = any([
        st.session_state.get("top_edad", "Todas") != "Todas",
        st.session_state.get("top_antiguedad", "Todas") != "Todas",
        st.session_state.get("top_cargo", "Todos") != "Todos",
    ])
    denom_invited = None if demographic_filter_active else (int(invited.get(selected_comp, 0)) if selected_comp != "Todas" else total_invited)
    participation = (n / denom_invited * 100) if denom_invited else None
    if demographic_filter_active:
        st.caption(f"Muestra del filtro: n={n} respuestas. El % de participación no se calcula por edad, antigüedad o cargo porque no conocemos cuántos comparsistas pertenecen a cada uno de esos segmentos.")
    elif n < 5:
        st.caption(f"Muestra del filtro: n={n} respuestas. Los resultados se muestran completos, pero conviene interpretarlos con cautela por el tamaño reducido de la muestra.")
    usage_n, usage = count_pct(filtered, "pulsera_usada", True)
    p7_n, p7 = count_pct(filtered, "pasacalles_preferencia", "Prefiero que pase a celebrarse el día 7")
    mf_n, mf = count_pct(filtered, "media_fiesta_preferencia", "Sí, me parece una buena propuesta")
    satisfaction = (float(avg) / 5 * 100) if not pd.isna(avg) else None

    if section == "Resumen":
        render_simple_summary(filtered, invited)

    elif section == "Decisiones clave":
        render_decisions_page(filtered)

    elif section == "Resumen general":
        cards = st.columns(5)
        render_kpi(cards[0], "Respuestas recibidas", f"{n}", "Respuestas del filtro actual", "👥", "#981b2b", "#f9e7ea")
        render_kpi(cards[1], "Participación", "—" if participation is None else f"{participation:.1f}%", f"{n} de {denom_invited} comparsistas" if denom_invited else "Configura el nº de comparsistas", "▥", "#d19a20", "#fbf2dd")
        render_kpi(cards[2], "Valoración general", "—" if pd.isna(avg) else f"{avg:.2f} / 5", "Media de satisfacción", "★", "#4c922d", "#eaf4e5")
        render_kpi(cards[3], "Recomendación", "—" if pd.isna(rec) else f"{rec:.1f} / 10", f"NPS {nps_score(filtered.get('recomendacion',pd.Series(dtype=float))):+.0f}", "👍", "#2169b4", "#e7f0fb")
        render_kpi(cards[4], "Comparsas activas", f"{filtered['comparsa'].nunique()} / 8", "Con respuestas en el filtro", "♟", "#74459a", "#f0e9f6")

        st.write("")
        rings = st.columns(5)
        render_ring(rings[0], "Satisfacción general", satisfaction, "Equivalencia de la media sobre 5", "#377e2d")
        render_ring(rings[1], "Participación", participation, f"{n} respuestas" + (f" de {denom_invited}" if denom_invited else ""), "#286db6")
        render_ring(rings[2], "Uso de pulsera", usage, f"{usage_n} personas la utilizaron", "#754b98")
        render_ring(rings[3], "Apoyo Pasacalles día 7", p7, f"{p7_n} personas prefieren el día 7", "#ed8b00")
        render_ring(rings[4], "Apoyo Media Fiesta 2 días", mf, f"{mf_n} personas están a favor", "#168d7a")

        st.write("")
        c1,c2,c3 = st.columns([1.13,1.05,1.05])
        comp_rows=[]
        for comp in COMPARSAS:
            sub=filtered[filtered['comparsa']==comp]
            resp=len(sub); inv=int(invited.get(comp,0)); pct=(resp/inv*100) if inv else np.nan
            comp_rows.append({"Comparsa":comp,"Respuestas":resp,"Comparsistas":inv,"Participación":pct})
        compdf=pd.DataFrame(comp_rows)
        with c1:
            st.markdown('<div class="admin-section-title">Participación por comparsa</div>', unsafe_allow_html=True)
            plot=compdf.copy(); plot["Etiqueta"]=[f"{int(r.Respuestas)}" + (f" · {r.Participación:.0f}%" if not pd.isna(r.Participación) else "") for _,r in plot.iterrows()]
            fig=px.bar(plot.sort_values("Respuestas"),x="Respuestas",y="Comparsa",orientation="h",text="Etiqueta")
            fig.update_traces(textposition="outside",hovertemplate="%{y}<br>%{x} respuestas<extra></extra>")
            fig.update_layout(height=430,margin=dict(t=8,b=25,l=10,r=40),xaxis_title="Respuestas",yaxis_title="",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig,use_container_width=True)
        with c2:
            st.markdown('<div class="admin-section-title">Valoración general por comparsa</div>', unsafe_allow_html=True)
            valrows=[]
            for comp in COMPARSAS:
                sub=filtered[filtered['comparsa']==comp]; value=pd.to_numeric(sub.get('valoracion_general'),errors='coerce').mean() if len(sub) else np.nan
                valrows.append({"Comparsa":comp,"Media":value})
            valdf=pd.DataFrame(valrows).dropna()
            fig=px.bar(valdf,x="Comparsa",y="Media",text="Media",range_y=[0,5])
            fig.update_traces(texttemplate="%{text:.2f}",textposition="outside")
            fig.update_layout(height=430,margin=dict(t=8,b=120,l=20,r=20),xaxis_tickangle=-45,xaxis_title="",yaxis_title="Media / 5",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig,use_container_width=True)
        with c3:
            st.markdown('<div class="admin-section-title">Ranking de actos · valoración media</div>', unsafe_allow_html=True)
            acts=acts_summary(filtered).dropna(subset=['Valoración media']).sort_values('Valoración media',ascending=False).head(12)
            if acts.empty:
                st.caption("Sin valoraciones de actos.")
            else:
                show=acts[["Acto","Valoración media","Respuestas que valoran"]].copy()
                show["Resultado"]=[f"{m:.2f}/5 · {int(nr)} votos" for m,nr in zip(show["Valoración media"],show["Respuestas que valoran"])]
                st.dataframe(show[["Acto","Resultado"]],use_container_width=True,hide_index=True,height=405)

        st.write("")
        p1,p2,p3,p4=st.columns([1,1,1,1.05])
        with p1:
            st.markdown('<div class="panel-box"><div class="panel-box-title">Pulsera festera</div><div class="panel-box-sub">Uso de la pulsera · número y porcentaje</div>',unsafe_allow_html=True)
            render_breakdown_list(filtered,"pulsera_usada",{True:"Sí",False:"No"})
            st.markdown('</div>',unsafe_allow_html=True)
            if "pulsera_utilidad" in filtered.columns:
                used=filtered[filtered.get("pulsera_usada",False)==True]
                st.plotly_chart(donut_chart(used,"pulsera_utilidad","Utilidad entre quienes la usaron"),use_container_width=True)
        with p2:
            st.markdown('<div class="panel-box"><div class="panel-box-title">Pasacalles festero</div><div class="panel-box-sub">Preferencia de día</div>',unsafe_allow_html=True)
            render_breakdown_list(filtered,"pasacalles_preferencia",{
                "Prefiero que pase a celebrarse el día 7":"Día 7",
                "Prefiero que se mantenga el día 8":"Día 8",
                "Me resulta indiferente":"Indiferente",
            })
            st.markdown('</div>',unsafe_allow_html=True)
            st.plotly_chart(donut_chart(filtered,"pasacalles_preferencia","Preferencia Pasacalles",{
                "Prefiero que pase a celebrarse el día 7":"Día 7",
                "Prefiero que se mantenga el día 8":"Día 8",
                "Me resulta indiferente":"Indiferente",
            }),use_container_width=True)
        with p3:
            st.markdown('<div class="panel-box"><div class="panel-box-title">Media Fiesta 2027</div><div class="panel-box-sub">Propuesta de dos días</div>',unsafe_allow_html=True)
            render_breakdown_list(filtered,"media_fiesta_preferencia",{
                "Sí, me parece una buena propuesta":"A favor",
                "No, prefiero que se mantenga el formato actual":"En contra",
                "Me resulta indiferente":"Indiferente",
            })
            st.markdown('</div>',unsafe_allow_html=True)
            st.plotly_chart(donut_chart(filtered,"media_fiesta_preferencia","Media Fiesta 2027",{
                "Sí, me parece una buena propuesta":"A favor",
                "No, prefiero que se mantenga el formato actual":"En contra",
                "Me resulta indiferente":"Indiferente",
            }),use_container_width=True)
        with p4:
            comments=recent_comment_rows(filtered,5)
            st.markdown('<div class="panel-box"><div class="panel-box-title">Comentarios recientes</div><div class="panel-box-sub">Últimas aportaciones escritas</div>',unsafe_allow_html=True)
            if not comments:
                st.caption("Todavía no hay comentarios escritos.")
            else:
                for label,comment in comments:
                    short=comment if len(comment)<=125 else comment[:122]+"…"
                    st.markdown(f'<div class="result-pill" style="display:block"><span class="answer">{label}</span><br><span style="color:#475467">“{short}”</span></div>',unsafe_allow_html=True)
            st.markdown('</div>',unsafe_allow_html=True)

        st.write("")
        a1,a2,a3,a4=st.columns(4)
        with a1:
            st.markdown('<div class="panel-box"><div class="panel-box-title">Evolución de las fiestas</div>',unsafe_allow_html=True)
            render_breakdown_list(filtered,"evolucion")
            st.markdown('</div>',unsafe_allow_html=True)
        with a2:
            st.markdown('<div class="panel-box"><div class="panel-box-title">Cantidad de actos</div>',unsafe_allow_html=True)
            render_breakdown_list(filtered,"cantidad_actos")
            st.markdown('</div>',unsafe_allow_html=True)
        with a3:
            st.markdown('<div class="panel-box"><div class="panel-box-title">Recomendación · NPS</div>',unsafe_allow_html=True)
            npsdf=nps_breakdown(filtered)
            if npsdf.empty: st.caption("Sin datos.")
            else:
                for _,r in npsdf.iterrows():
                    st.markdown(f'<div class="result-pill"><span class="answer">{r["Respuesta"]}</span><span class="number">{int(r["Personas"])} · {r["Porcentaje"]:.1f}%</span></div>',unsafe_allow_html=True)
                st.markdown(f'<div style="margin-top:8px">NPS: <span class="small-stat">{nps_score(filtered.get("recomendacion",pd.Series(dtype=float))):+.0f}</span></div>',unsafe_allow_html=True)
            st.markdown('</div>',unsafe_allow_html=True)
        with a4:
            rank=ranking_summary(filtered).head(3)
            st.markdown('<div class="panel-box"><div class="panel-box-title">3 actos preferidos</div><div class="panel-box-sub">Resultado ponderado de la selección</div>',unsafe_allow_html=True)
            if rank.empty: st.caption("Sin datos.")
            else:
                for i,(_,r) in enumerate(rank.iterrows(),1):
                    st.markdown(f'<div class="result-pill"><span class="answer">{i}. {r["Acto"]}</span><span class="number">{int(r["Puntuación total"])} pts</span></div>',unsafe_allow_html=True)
            st.markdown('</div>',unsafe_allow_html=True)

        st.markdown("### Lectura rápida")
        for pt in interpretation_points(filtered, invited): st.markdown(f"- {pt}")

    elif section == "Comparsas":
        rows=[]
        for comp in COMPARSAS:
            sub=df[df['comparsa']==comp]
            inv=int(invited.get(comp,0)); resp=len(sub)
            avgv=pd.to_numeric(sub.get('valoracion_general'),errors='coerce').mean() if resp else np.nan
            recv=pd.to_numeric(sub.get('recomendacion'),errors='coerce').mean() if resp else np.nan
            use_n,use_pct=count_pct(sub,'pulsera_usada',True)
            d7_n,d7_pct=count_pct(sub,'pasacalles_preferencia','Prefiero que pase a celebrarse el día 7')
            mf_c,mf_pct=count_pct(sub,'media_fiesta_preferencia','Sí, me parece una buena propuesta')
            rows.append({
                'Comparsa':comp,'Respuestas':resp,'Comparsistas':inv,
                '% Participación':round(resp/inv*100,1) if inv else np.nan,
                'Valoración general':round(avgv,2) if not pd.isna(avgv) else np.nan,
                'Recomendación':round(recv,1) if not pd.isna(recv) else np.nan,
                'Uso pulsera':f'{use_n} ({use_pct:.1f}%)' if resp else '—',
                'Apoyo día 7':f'{d7_n} ({d7_pct:.1f}%)' if resp else '—',
                'Media Fiesta 2 días':f'{mf_c} ({mf_pct:.1f}%)' if resp else '—',
            })
        compdf=pd.DataFrame(rows)
        st.dataframe(compdf,use_container_width=True,hide_index=True)
        st.markdown("### Comparación de cada comparsa frente al total")
        st.caption("Los valores Δ muestran cuánto se separa cada comparsa del resultado global. Por ejemplo, +10 en apoyo al día 7 significa 10 puntos porcentuales por encima del total.")
        comparison = comparison_by_comparsa(df)
        if not comparison.empty:
            st.dataframe(comparison,use_container_width=True,hide_index=True)
        a,b=st.columns(2)
        with a:
            plot=compdf.dropna(subset=['Valoración general'])
            fig=px.bar(plot,x='Comparsa',y='Valoración general',range_y=[0,5],text='Valoración general',title='Valoración general por comparsa')
            fig.update_traces(textposition='outside'); fig.update_layout(xaxis_tickangle=-35,height=450)
            st.plotly_chart(fig,use_container_width=True)
        with b:
            plot=compdf.dropna(subset=['% Participación'])
            fig=px.bar(plot,x='Comparsa',y='% Participación',range_y=[0,100],text='% Participación',title='Participación por comparsa (%)')
            fig.update_traces(texttemplate='%{text:.1f}%',textposition='outside'); fig.update_layout(xaxis_tickangle=-35,height=450)
            st.plotly_chart(fig,use_container_width=True)
        with st.expander("Configurar número de comparsistas por comparsa"):
            new_counts={}; cols=st.columns(2)
            for i,c in enumerate(COMPARSAS):
                with cols[i%2]: new_counts[c]=st.number_input(c,min_value=0,max_value=10000,value=int(invited.get(c,0)),step=1,key=f'inv_{i}')
            if st.button("Guardar configuración",type="primary"):
                ok,msg=save_invited_counts(new_counts); (st.success if ok else st.error)(msg)

    elif section == "Actos":
        acts=acts_summary(filtered).sort_values('Valoración media',ascending=False)
        rank=ranking_summary(filtered)
        a,b=st.columns(2)
        with a:
            fig=px.bar(acts.dropna(subset=['Valoración media']).sort_values('Valoración media'),x='Valoración media',y='Acto',orientation='h',range_x=[0,5],title='Ranking por valoración media',text='Valoración media')
            fig.update_traces(texttemplate='%{text:.2f}',textposition='outside'); fig.update_layout(height=590)
            st.plotly_chart(fig,use_container_width=True)
        with b:
            if not rank.empty:
                fig=px.bar(rank.sort_values('Puntuación total'),x='Puntuación total',y='Acto',orientation='h',title='3 actos preferidos · puntuación total',text='Puntuación total')
                fig.update_traces(textposition='outside'); fig.update_layout(height=590)
                st.plotly_chart(fig,use_container_width=True)
        st.markdown("### Resumen por acto")
        st.dataframe(acts,use_container_width=True,hide_index=True)
        selected_act=st.selectbox("Ver distribución de valoraciones de un acto",list(ACTOS.values()),key='admin_act_detail')
        act_key=next((k for k,v in ACTOS.items() if v==selected_act),None)
        if act_key:
            vals=pd.to_numeric(filtered.get(act_key),errors='coerce').dropna().astype(int)
            if vals.empty:
                st.info("Todavía no hay valoraciones para este acto.")
            else:
                dist=vals.value_counts().reindex([1,2,3,4,5],fill_value=0).reset_index(); dist.columns=['Valoración','Personas']; dist['Porcentaje']=dist['Personas']/len(vals)*100
                fig=px.bar(dist,x='Valoración',y='Personas',text='Personas',title=f'Distribución · {selected_act}')
                st.plotly_chart(fig,use_container_width=True)
                st.dataframe(dist.round({'Porcentaje':1}),use_container_width=True,hide_index=True)
        if not rank.empty:
            st.markdown("### Resultado de los 3 actos preferidos")
            st.caption("Cada encuestado elige 3 actos: 1 punto al tercero favorito, 2 al segundo y 3 al favorito.")
            st.dataframe(rank,use_container_width=True,hide_index=True)

    elif section == "Pulsera festera":
        a,b=st.columns(2)
        with a:
            st.plotly_chart(donut_chart(filtered,'pulsera_usada','¿Utilizó la pulsera?',{True:'Sí',False:'No'}),use_container_width=True)
            st.markdown("#### Número y porcentaje")
            render_breakdown_list(filtered,'pulsera_usada',{True:'Sí',False:'No'})
        used=filtered[filtered.get('pulsera_usada',False)==True]
        with b:
            if not used.empty and 'pulsera_utilidad' in used:
                st.plotly_chart(donut_chart(used,'pulsera_utilidad','Utilidad percibida'),use_container_width=True)
                st.markdown("#### Número y porcentaje")
                render_breakdown_list(used,'pulsera_utilidad')
        val=pd.to_numeric(used.get('pulsera_valoracion'),errors='coerce').dropna() if not used.empty else pd.Series(dtype=float)
        st.metric("Valoración media de la pulsera", "—" if val.empty else f"{val.mean():.2f} / 5", f"{len(val)} personas la valoraron")
        if not val.empty:
            dist=val.astype(int).value_counts().reindex([1,2,3,4,5],fill_value=0).reset_index(); dist.columns=['Valoración','Personas']; dist['Porcentaje']=(dist['Personas']/len(val)*100).round(1)
            st.dataframe(dist,use_container_width=True,hide_index=True)

    elif section == "Pasacalles festero":
        labels={"Prefiero que pase a celebrarse el día 7":"Día 7","Prefiero que se mantenga el día 8":"Día 8","Me resulta indiferente":"Indiferente"}
        a,b=st.columns([1.1,1])
        with a: st.plotly_chart(donut_chart(filtered,'pasacalles_preferencia','Preferencia sobre el día del Pasacalles Festero',labels),use_container_width=True)
        with b:
            st.markdown("### Resultado exacto")
            render_breakdown_list(filtered,'pasacalles_preferencia',labels)
        vals=filtered.get('pasacalles_motivo',pd.Series(dtype=str)).fillna('').astype(str).str.strip(); vals=vals[vals!='']
        st.markdown(f"### Motivos escritos ({len(vals)})")
        for value in vals.head(200): st.markdown(f"- {value}")

    elif section == "Media Fiesta 2027":
        labels={"Sí, me parece una buena propuesta":"A favor","No, prefiero que se mantenga el formato actual":"En contra","Me resulta indiferente":"Indiferente"}
        a,b=st.columns([1.1,1])
        with a: st.plotly_chart(donut_chart(filtered,'media_fiesta_preferencia','Media Fiesta 2027 en dos días',labels),use_container_width=True)
        with b:
            st.markdown("### Resultado exacto")
            render_breakdown_list(filtered,'media_fiesta_preferencia',labels)
        vals=filtered.get('media_fiesta_comentarios',pd.Series(dtype=str)).fillna('').astype(str).str.strip(); vals=vals[vals!='']
        st.markdown(f"### Comentarios ({len(vals)})")
        for value in vals.head(200): st.markdown(f"- {value}")

    elif section == "Castillo Festero":
        labels={
            "Sí, me gustaría que estuviese allí.":"Sí · Avenida de la Constitución",
            "No, prefiero que se mantenga en su ubicación actual.":"No · Ubicación actual",
            "Me es indiferente / No tengo una preferencia clara.":"Indiferente",
        }
        st.markdown("### Castillo Festero · Avenida de la Constitución")
        st.caption("Resultado de la pregunta sobre la posible ubicación del Castillo Festero. Los filtros superiores se aplican también a este análisis.")
        a,b=st.columns([1.1,1])
        with a:
            st.plotly_chart(donut_chart(filtered,'castillo_avenida','¿Castillo Festero en la Avenida de la Constitución?',labels),use_container_width=True)
        with b:
            st.markdown("### Resultado exacto")
            render_breakdown_list(filtered,'castillo_avenida',labels)

    elif section == "Comentarios":
        st.markdown("### Comentarios de los festeros")
        st.caption("Primero tienes un resumen sencillo de los temas que más se repiten. Si quieres profundizar, abre la pestaña ‘Leer comentarios’.")
        comments=comment_records(filtered)
        if comments.empty:
            st.info("Todavía no hay comentarios escritos en el filtro actual.")
        else:
            comments["Tema"] = comments["Comentario"].map(comment_theme)
            surveys_with_comment = comments["RespuestaID"].replace('', np.nan).nunique()
            total_comments = len(comments)
            theme_counts=comments["Tema"].value_counts().reset_index()
            theme_counts.columns=["Tema","Comentarios"]
            theme_counts["Porcentaje"]=(theme_counts["Comentarios"]/total_comments*100).round(1)
            top_theme = theme_counts.iloc[0]["Tema"] if not theme_counts.empty else "—"
            top_theme_n = int(theme_counts.iloc[0]["Comentarios"]) if not theme_counts.empty else 0

            k1,k2,k3=st.columns(3)
            k1.metric("Encuestas con algún comentario", int(surveys_with_comment), "Personas que escribieron al menos una aportación")
            k2.metric("Aportaciones escritas", total_comments, "Un festero puede escribir en varios apartados")
            k3.metric("Tema más repetido", str(top_theme), f"{top_theme_n} menciones")

            tab_summary, tab_read = st.tabs(["📌 Resumen de opiniones", "💬 Leer comentarios"])
            with tab_summary:
                a,b=st.columns([1.15,1])
                with a:
                    st.markdown("#### Temas que más se repiten")
                    plot=theme_counts.sort_values("Comentarios",ascending=True).copy()
                    plot["Etiqueta"] = plot.apply(lambda r: f'{int(r["Comentarios"])} · {r["Porcentaje"]:.1f}%', axis=1)
                    fig=px.bar(plot,x="Comentarios",y="Tema",orientation="h",text="Etiqueta")
                    fig.update_traces(textposition="outside",hovertemplate="%{y}<br>%{x} comentarios<extra></extra>")
                    fig.update_layout(height=max(320,60*len(plot)),margin=dict(t=10,b=20,l=10,r=70),xaxis_title="Número de comentarios",yaxis_title="",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig,use_container_width=True)
                with b:
                    st.markdown("#### Dónde han escrito")
                    cat=comments["Categoría"].value_counts().reset_index()
                    cat.columns=["Apartado","Comentarios"]
                    cat["Porcentaje"]=(cat["Comentarios"]/total_comments*100).round(1)
                    for _,r in cat.iterrows():
                        st.markdown(f'<div class="result-pill"><span class="answer">{r["Apartado"]}</span><span class="number">{int(r["Comentarios"])} · {r["Porcentaje"]:.1f}%</span></div>',unsafe_allow_html=True)

                st.markdown("#### Lectura rápida")
                for _,r in theme_counts.head(5).iterrows():
                    st.markdown(f'- **{r["Tema"]}:** {int(r["Comentarios"])} menciones ({r["Porcentaje"]:.1f}% de las aportaciones escritas).')
                st.caption("La clasificación por temas es automática y sirve para localizar patrones; para una decisión importante conviene leer los comentarios concretos.")

            with tab_read:
                st.markdown("#### Buscar y filtrar")
                f1,f2,f3=st.columns([1,1,1])
                with f1:
                    theme=st.selectbox("Tema",["Todos"]+sorted(comments["Tema"].unique().tolist()),key="comment_theme_filter")
                with f2:
                    category=st.selectbox("Apartado",["Todos"]+sorted(comments["Categoría"].unique().tolist()),key="comment_category_filter")
                with f3:
                    comparsa=st.selectbox("Comparsa",["Todas"]+sorted(comments["Comparsa"].dropna().unique().tolist()),key="comment_comparsa_filter")
                search=st.text_input("Buscar una palabra o frase",placeholder="Ej.: horarios, pulsera, desfile...",key="comment_search")

                shown=comments.copy()
                if theme!="Todos": shown=shown[shown["Tema"]==theme]
                if category!="Todos": shown=shown[shown["Categoría"]==category]
                if comparsa!="Todas": shown=shown[shown["Comparsa"]==comparsa]
                if search.strip(): shown=shown[shown["Comentario"].str.contains(search.strip(),case=False,na=False,regex=False)]

                st.markdown(f"#### {len(shown)} comentario(s) encontrado(s)")
                if shown.empty:
                    st.info("No hay comentarios que coincidan con esos filtros.")
                else:
                    for idx,(_,r) in enumerate(shown.head(150).iterrows(),1):
                        title=f'{r["Tema"]} · {r["Comparsa"] or "Sin comparsa"}'
                        with st.expander(title, expanded=idx<=3):
                            st.write(r["Comentario"])
                            meta=[]
                            if r.get("Categoría"): meta.append(f'**Apartado:** {r["Categoría"]}')
                            if r.get("Edad"): meta.append(f'**Edad:** {r["Edad"]}')
                            if r.get("Fecha"): meta.append(f'**Fecha:** {r["Fecha"]}')
                            st.caption(" · ".join(meta))
                    if len(shown)>150:
                        st.info(f"Se muestran los primeros 150 de {len(shown)} comentarios. Usa los filtros o el buscador para acotar la búsqueda.")

                export_cols=["Fecha","Tema","Categoría","Comparsa","Edad","Comentario"]
                csv_comments=shown[export_cols].to_csv(index=False).encode('utf-8-sig')
                st.download_button("Descargar comentarios filtrados (CSV)",csv_comments,file_name="comentarios_filtrados.csv",mime="text/csv",use_container_width=True)

    elif section == "Informes":
        st.markdown("### Generar informes para la Junta Directiva")
        scope=st.selectbox("Ámbito del informe",["TOTAL"]+COMPARSAS)
        report_df=df if scope=="TOTAL" else df[df['comparsa']==scope]
        if report_df.empty:
            st.info("No hay respuestas disponibles para este ámbito.")
        else:
            render_executive_interpretation(report_df,invited)
            st.info("El Excel incluye la interpretación automática, distribuciones con número de personas y porcentaje y, cuando existen, los temas recurrentes de los comentarios.")
            csv=report_df.drop(columns=['id','excluded'],errors='ignore').to_csv(index=False).encode('utf-8-sig')
            excel=report_excel_bytes(report_df,invited)
            scope_label="Todas las comparsas" if scope=='TOTAL' else scope
            pdf=report_pdf_bytes(report_df,scope_label,invited)
            easy_pdf=simple_report_pdf_bytes(report_df,scope_label,invited)
            st.markdown("#### Dos formas de presentar los resultados")
            r1,r2=st.columns(2)
            with r1:
                st.success("""**Informe resumido**

Pensado para reuniones: portada institucional, cifras clave, decisiones y conclusiones. Lectura aproximada: 2–3 minutos.""")
                st.download_button("Descargar INFORME RESUMIDO (PDF)",easy_pdf,file_name=f"informe_resumido_{scope.lower().replace(' ','_')}.pdf",mime='application/pdf',use_container_width=True,type='primary')
            with r2:
                st.info("""**Informe completo**

Documento institucional con portada, escudo, comparsas, actos, ranking, interpretación y conclusiones.""")
                st.download_button("Descargar INFORME COMPLETO (PDF)",pdf,file_name=f"informe_completo_{scope.lower().replace(' ','_')}.pdf",mime='application/pdf',use_container_width=True)
            st.markdown("#### Datos para trabajar")
            d1,d2=st.columns(2)
            d1.download_button("Descargar Excel detallado",excel,file_name=f"informe_{scope.lower().replace(' ','_')}.xlsx",mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
            d2.download_button("Descargar CSV de respuestas",csv,file_name=f"resultados_{scope.lower().replace(' ','_')}.csv",mime='text/csv',use_container_width=True)
            st.caption("Los informes no incluyen nombre, DNI, email ni teléfono porque la encuesta no solicita esos datos.")

    elif section == "Gestionar encuestas":
        st.markdown("### Administración de encuestas")
        st.info("Puedes excluir una encuesta del análisis sin borrarla. Las excluidas pueden recuperarse después. Utiliza el borrado permanente solo cuando sea necesario.")
        manage = all_df.copy()
        if manage.empty:
            st.success("La base de datos está limpia: actualmente hay 0 encuestas registradas.")
            return
        manage["excluded"] = manage.get("excluded", False).fillna(False).astype(bool)
        manage["created_at"] = pd.to_datetime(manage.get("created_at"), errors="coerce")
        manage["Fecha"] = manage["created_at"].dt.strftime("%d/%m/%Y %H:%M").fillna("")
        manage["Estado"] = np.where(manage["excluded"], "Excluida", "Activa")
        manage["Etiqueta"] = manage.apply(lambda r: f"{r['Fecha']} · {r.get('comparsa','')} · {r.get('edad','')} · ID {str(r.get('id',''))[:8]}", axis=1)
        labels = manage["Etiqueta"].tolist()
        selected_labels = st.multiselect("Selecciona las encuestas que quieres gestionar", labels, placeholder="Puedes seleccionar una o varias")
        selected_ids = manage.loc[manage["Etiqueta"].isin(selected_labels), "id"].astype(str).tolist()
        st.dataframe(manage[["Fecha","Estado","comparsa","edad","antiguedad","cargo"]].rename(columns={"comparsa":"Comparsa","edad":"Edad","antiguedad":"Antigüedad","cargo":"Cargo"}), use_container_width=True, hide_index=True)
        a,b,c = st.columns(3)
        with a:
            if st.button("Excluir del análisis", use_container_width=True, disabled=not selected_ids):
                ok, msg = set_responses_excluded(selected_ids, True)
                (st.success if ok else st.error)(msg)
                if ok: st.rerun()
        with b:
            if st.button("Recuperar excluidas", use_container_width=True, disabled=not selected_ids):
                ok, msg = set_responses_excluded(selected_ids, False)
                (st.success if ok else st.error)(msg)
                if ok: st.rerun()
        with c:
            if st.button("Borrar seleccionadas", type="primary", use_container_width=True, disabled=not selected_ids):
                ok, msg = delete_responses(selected_ids)
                (st.success if ok else st.error)(msg)
                if ok: st.rerun()
        st.markdown("---")
        col_all, _ = st.columns([1,2])
        with col_all:
            st.markdown("**Vaciar todas las respuestas**")
            confirmation = st.text_input('Para borrar todas, escribe exactamente: BORRAR TODAS', key='delete_all_confirmation')
            if st.button("Borrar TODAS las encuestas", use_container_width=True, disabled=confirmation != "BORRAR TODAS"):
                ok, msg = delete_all_responses()
                (st.success if ok else st.error)(msg)
                if ok:
                    st.session_state.pop('delete_all_confirmation', None)
                    st.rerun()

    elif section == "Cómo interpretar":
        st.markdown("### Interpretación de resultados")
        st.info("Esta es la lectura avanzada. Para una explicación mucho más sencilla, utilice primero ‘Resumen’. Esta sección se recalcula con los filtros activos y aporta el razonamiento y los datos que justifican las conclusiones.")
        render_executive_interpretation(filtered,invited)
        st.markdown("### Cómo leer cada indicador")
        g1,g2=st.columns(2)
        with g1:
            st.markdown("**Valoración general (1–5).** Por encima de 4 indica satisfacción alta; entre 3 y 4 hay satisfacción moderada; por debajo de 3 conviene revisar el área en profundidad.")
            st.markdown("**Número + porcentaje.** El porcentaje permite comparar grupos de distinto tamaño; el número de personas muestra el peso real de esa opinión. Deben leerse juntos.")
            st.markdown("**Actos.** La media de 1–5 indica satisfacción; el ranking de 3 favoritos mide preferencia. Un acto puede tener buena valoración y no ser de los tres favoritos, y viceversa.")
        with g2:
            st.markdown("**NPS.** 9–10 son promotores, 7–8 pasivos y 0–6 detractores. NPS = % promotores − % detractores. Un valor positivo es mejor que uno negativo, pero debe interpretarse junto con la media de recomendación.")
            st.markdown("**Comparsas y filtros.** Una media global puede ocultar diferencias. Conviene repetir la lectura por comparsa, edad, antigüedad y responsabilidad festera antes de tomar decisiones importantes.")
            st.markdown("**Comentarios abiertos.** La detección de temas recurrentes sirve para encontrar patrones. Es recomendable leer después los comentarios completos que explican esos patrones.")

# =============================================================
# ROUTER
# =============================================================

view = st.query_params.get("view", "encuesta")

# V21: en la encuesta pública se elimina por completo la cabecera nativa de Streamlit.
# En el panel de Junta se conserva la estructura necesaria para la navegación lateral.
if view != "admin":
    st.markdown(
        """
        <style>
        header[data-testid="stHeader"],
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stHeaderActionElements"],
        [data-testid="stAppDeployButton"],
        [data-testid="stViewerBadge"],
        [data-testid="manage-app-button"],
        #MainMenu {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

if view == "admin":
    render_admin()
else:
    render_survey()
