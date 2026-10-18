import os
import json
import io
import urllib.parse
import urllib.request
import glob
import pandas as pd
import plotly.express as px
import streamlit as st

# Imports voor PDF & Vector Grafieken (Pure Python, Geen Kaleido nodig)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

APP_VERSION = "3.9.0"

# --- CONFIGURATIE ---
SERVER_PHP_URL = "https://team-level-up.com/otsv/get_matches.php"
SERVER_DATA_BASE_URL = "https://team-level-up.com/otsv/data/"
STREAMLIT_CLOUD_URL = "https://voetbalobservatietool-supifuf6eqyrufsb9vdbch.streamlit.app"

EVENT_VALUES = {
    # Aanvallen - Opbouwen
    "Balverlies eigen helft": -2,
    "Balverlies helft tegenpartij": -1,
    "Creëren van een scoringskans": 2,
    # Aanvallen - Scoren
    "Missen van een scoringskans": 1,
    "Redding van keeper of schot geblokt": 2,
    "Benutten van een scoringskans": 3,
    # Verdedigen - Verstoren opbouw
    "Balwinst helft tegenpartij": 2,
    "Balwinst eigen helft": 1,
    "Tegenpartij creëert scoringskans": -1,
    # Verdedigen - Voorkomen van scoren
    "Tegenpartij mist de scoringskans": 0,
    "Tegenpartij benut scoringskans": -3
}

COLOR_MAP_WAARDE = {
    "-3": "#c0392b",
    "-2": "#e74c3c",
    "-1": "#e67e22",
     "0": "#f39c12",
    "+1": "#f1c40f",
    "+2": "#2ecc71",
    "+3": "#27ae60"
}

st.set_page_config(
    page_title=f"Voetbal Observatie Dashboard v{APP_VERSION}",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Voetbal Observatie Dashboard")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
match_data = None
current_token = None
selected_filename = None

query_params = st.query_params
token_param = query_params.get("token", None)

is_local = os.path.exists(DATA_DIR) and not os.environ.get("STREAMLIT_SERVER_GATHER_USAGE_STATS", False)

# --- 1. BEVEILIGDE ONTSLUITING VIA TOKEN ---
if token_param:
    current_token = token_param
    try:
        token_resolve_url = f"{SERVER_PHP_URL}?token={token_param}"
        req = urllib.request.Request(token_resolve_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            token_res = json.loads(resp.read().decode('utf-8'))

            if token_res.get("status") == "success":
                selected_filename = token_res["filename"]
                file_url = SERVER_DATA_BASE_URL + selected_filename
                file_req = urllib.request.Request(file_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(file_req) as f_resp:
                    match_data = json.loads(f_resp.read().decode('utf-8'))
                st.sidebar.success("🔒 Beveiligde wedstrijd-link geactiveerd")
            else:
                st.error("❌ Ongeldige of verlopen link-token.")
    except Exception as e:
        st.error(f"Fout bij het ophalen van de wedstrijddata: {e}")

# --- 2. LOKALE BEHEERDER MODUS ---
if not match_data:
    if is_local:
        st.sidebar.header("🔍 Wedstrijd Selectie (Lokaal/Beheerder)")
        matches_list = []

        if os.path.exists(DATA_DIR):
            local_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), key=os.path.getmtime, reverse=True)
            for f_path in local_files:
                fname = os.path.basename(f_path)
                if fname == "tokens.json": continue
                try:
                    with open(f_path, "r", encoding="utf-8") as f_obj:
                        content = json.load(f_obj)
                        w_info = content.get("wedstrijd", {})
                        wij = w_info.get("wij", "Wij")
                        zij = w_info.get("zij", "Zij")
                        datum_raw = w_info.get("datum", "")

                        if datum_raw and "T" in datum_raw:
                            d_part, t_part = datum_raw.split("T")
                            jaar, maand, dag = d_part.split("-")
                            tijd_str = t_part[:5]
                            datum_formatted = f"{dag}-{maand}-{jaar} {tijd_str}"
                        else:
                            datum_formatted = fname

                        label = f"{wij} vs {zij} ({datum_formatted})"
                except:
                    label = fname
                matches_list.append({"filename": fname, "label": label})

        if matches_list:
            labels = [m["label"] for m in matches_list]
            selected_label = st.sidebar.selectbox("Kies een opgeslagen wedstrijd:", labels)
            selected_match_info = matches_list[labels.index(selected_label)]
            selected_filename = selected_match_info["filename"]

            with open(os.path.join(DATA_DIR, selected_filename), "r", encoding="utf-8") as f:
                match_data = json.load(f)
        else:
            uploaded_file = st.sidebar.file_uploader("Upload handmatig een JSON wedstrijd-bestand:", type=["json"])
            if uploaded_file:
                match_data = json.load(uploaded_file)
    else:
        st.warning("🔒 Toegang geweigerd. Deze online omgeving vereist een geldige wedstrijd-link (token).")
        st.info("Open een geselecteerde wedstrijd rechtstreeks vanuit de observatietool op team-level-up.com.")
        st.sidebar.markdown("---")
        st.sidebar.caption(f"Dashboard Versie: **v{APP_VERSION}**")
        st.stop()

# --- 3. DELEN FUNCTIONALITEIT ---
if match_data:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔗 Dashboard Delen")

    if not current_token and selected_filename and is_local:
        try:
            token_query_url = f"{SERVER_PHP_URL}?get_token_for={urllib.parse.quote(selected_filename)}"
            req = urllib.request.Request(token_query_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                t_res = json.loads(resp.read().decode('utf-8'))
                if t_res.get("status") == "success":
                    current_token = t_res["token"]
        except:
            pass

    if current_token:
        share_url = f"{STREAMLIT_CLOUD_URL}/?token={current_token}"
        st.sidebar.caption("Kopieer deze beveiligde token-link:")
        st.sidebar.code(share_url, language=None)

        qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(share_url)}"
        with st.sidebar.popover("📱 Toon QR-Code om te scannen"):
            st.image(qr_api_url, caption="Scan met telefooncamera om te openen", width=150)

if not match_data:
    st.stop()

# --- 4. DATA VERWERKING EN DASHBOARD WEERGAVE ---
wedstrijd_info = match_data.get("wedstrijd", {})
observaties = match_data.get("observaties", [])
file_version = match_data.get("versie", "1.0.0")

st.sidebar.markdown("---")
st.sidebar.subheader("📋 Wedstrijd Details")
st.sidebar.write(f"**Team (Wij):** {wedstrijd_info.get('wij', 'Wij')}")
st.sidebar.write(f"**Tegenpartij (Zij):** {wedstrijd_info.get('zij', 'Zij')}")
st.sidebar.write(f"**Duur per helft:** {wedstrijd_info.get('duur_per_helft_minuten', '-')} min")
st.sidebar.write(f"**Verlenging:** {'Ja' if wedstrijd_info.get('verlenging_mogelijk') else 'Nee'}")
if "datum" in wedstrijd_info:
    datum_raw = wedstrijd_info['datum']
    if "T" in datum_raw:
        d_p, t_p = datum_raw.split("T")
        j, m, d = d_p.split("-")
        st.sidebar.write(f"📅 **Datum & Tijd:** {d}-{m}-{j} {t_p[:5]}")
    else:
        st.sidebar.write(f"📅 **Datum:** {datum_raw}")

st.sidebar.markdown("---")
st.sidebar.caption(f"Dashboard Versie: **v{APP_VERSION}**")
st.sidebar.caption(f"Data Formaat Versie: **v{file_version}**")

if not observaties:
    st.warning("Er zijn geen geobserveerde gebeurtenissen gevonden in dit bestand.")
    st.stop()

df = pd.DataFrame(observaties)

def time_to_minutes(t_str):
    try:
        parts = str(t_str).split(":")
        minutes = int(parts[0])
        seconds = int(parts[1]) if len(parts) > 1 else 0
        return minutes + (seconds / 60.0)
    except:
        return 0.0

df["minuut_float"] = df["tijd"].apply(time_to_minutes)
df["minuut_int"] = df["minuut_float"].astype(int)

if "waarde" not in df.columns:
    df["waarde"] = df["event"].map(EVENT_VALUES).fillna(0).astype(int)
else:
    df["waarde"] = df["waarde"].fillna(df["event"].map(EVENT_VALUES)).fillna(0).astype(int)

df["waarde_str"] = df["waarde"].apply(lambda x: f"+{int(x)}" if x > 0 else str(int(x)))

# Score Berekening
goals_wij = len(df[(df["functie"] == "Aanvallen") & (df["event"] == "Benutten van een scoringskans")])
goals_zij = len(df[(df["functie"] == "Verdedigen") & (df["event"] == "Tegenpartij benut scoringskans")])

totaal_acties = len(df)
aanval_acties = len(df[df["functie"] == "Aanvallen"])
verdedig_acties = len(df[df["functie"] == "Verdedigen"])
scoringskansen = len(df[df["event"].str.contains("scoringskans", case=False, na=False)])

team_wij_naam = wedstrijd_info.get('wij', 'Wij')
team_zij_naam = wedstrijd_info.get('zij', 'Zij')

st.markdown(
    f"""
    <div style="text-align: center; background-color: #242438; padding: 12px; border-radius: 10px; margin-bottom: 15px;">
        <span style="color: #2ecc71; font-size: 26px; font-weight: bold;">{team_wij_naam}</span>
        <span style="color: #ffffff; font-size: 28px; font-weight: bold; margin: 0 15px;">{goals_wij} - {goals_zij}</span>
        <span style="color: #95a5a6; font-size: 26px; font-weight: bold;">{team_zij_naam
