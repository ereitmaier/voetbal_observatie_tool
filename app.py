import os
import json
import base64
import urllib.parse
import urllib.request
import glob
import pandas as pd
import plotly.express as px
import streamlit as st

APP_VERSION = "2.3.0"

# Pas dit aan naar de URL van jouw webserver waar get_matches.php staat
SERVER_PHP_URL = "https://jouw-domein.nl/get_matches.php"
SERVER_DATA_BASE_URL = "https://jouw-domein.nl/data/"

st.set_page_config(
    page_title=f"Voetbal Observatie Dashboard v{APP_VERSION}",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Voetbal Observatie Dashboard")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
match_data = None

# --- 1. DIRECTE DATA VIA URL PARAMETER ---
query_params = st.query_params
encoded_data = query_params.get("data", None)

if encoded_data:
    try:
        decoded_bytes = base64.b64decode(urllib.parse.unquote(encoded_data))
        match_data = json.loads(decoded_bytes.decode("utf-8"))
        st.caption("⚡ Wedstrijd direct geladen vanuit observatietool.")
    except Exception as e:
        st.error(f"Fout bij het uitlezen van URL data: {e}")

# --- 2. WEDSTRIJDEN OPHALEN VAN SERVER / LOKALE MAP ---
if not match_data:
    st.sidebar.header("🔍 Wedstrijd Selectie")

    matches_list = []

    # Check A: Lokale /data/ map (Desktop modus)
    if os.path.exists(DATA_DIR):
        local_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
        for f in local_files:
            fname = os.path.basename(f)
            matches_list.append({"filename": fname, "label": fname, "type": "local"})

    # Check B: Ophalen via PHP server (Streamlit Cloud modus)
    if not matches_list and SERVER_PHP_URL:
        try:
            req = urllib.request.Request(SERVER_PHP_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    server_matches = json.loads(response.read().decode('utf-8'))
                    for m in server_matches:
                        m["type"] = "server"
                        matches_list.append(m)
        except Exception as e:
            st.sidebar.warning("⚠️ Kon geen verbinding maken met de PHP server.")

    # Weergave van het keuzemenu
    if matches_list:
        labels = [m["label"] for m in matches_list]
        requested_match = query_params.get("match", None)

        default_idx = 0
        if requested_match:
            for idx, m in enumerate(matches_list):
                if m["filename"] == requested_match:
                    default_idx = idx
                    break

        selected_label = st.sidebar.selectbox("Kies een opgeslagen wedstrijd van de server:", labels, index=default_idx)
        selected_match_info = matches_list[labels.index(selected_label)]

        # Laden van het gekozen bestand
        if selected_match_info["type"] == "local":
            with open(os.path.join(DATA_DIR, selected_match_info["filename"]), "r", encoding="utf-8") as f:
                match_data = json.load(f)
        else:
            file_url = SERVER_DATA_BASE_URL + selected_match_info["filename"]
            with urllib.request.urlopen(file_url) as resp:
                match_data = json.loads(resp.read().decode('utf-8'))
    else:
        uploaded_file = st.sidebar.file_uploader("Upload een JSON bestand:", type=["json"])
        if uploaded_file:
            match_data = json.load(uploaded_file)

if not match_data:
    st.info("👋 Welkom! Er is nog geen wedstrijd geladen. Kies een wedstrijd in de sidebar of voer een observatie uit.")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"App Versie: **v{APP_VERSION}**")
    st.stop()

wedstrijd_info = match_data.get("wedstrijd", {})
observaties = match_data.get("observaties", [])
file_version = match_data.get("versie", "1.0.0")

st.sidebar.markdown("---")
st.sidebar.subheader("📋 Wedstrijd Details")
st.sidebar.write(f"**Team (Wij):** {wedstrijd_info.get('wij', 'Onbekend')}")
st.sidebar.write(f"**Tegenpartij (Zij):** {wedstrijd_info.get('zij', 'Onbekend')}")
st.sidebar.write(f"**Duur per helft:** {wedstrijd_info.get('duur_per_helft_minuten', '-')} min")
st.sidebar.write(f"**Verlenging:** {'Ja' if wedstrijd_info.get('verlenging_mogelijk') else 'Nee'}")
if "datum" in wedstrijd_info:
    st.sidebar.write(f"📅 **Datum:** {wedstrijd_info['datum'][:10]}")

st.sidebar.markdown("---")
st.sidebar.caption(f"Dashboard Versie: **v{APP_VERSION}**")

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
        <span style="color: #95a5a6; font-size: 26px; font-weight: bold;">{team_zij_naam}</span>
    </div>
    """,
    unsafe_allow_html=True
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Uitslag", f"{goals_wij} - {goals_zij}")
col2.metric("Aanvallende Acties", aanval_acties, f"{round(aanval_acties/totaal_acties*100)}%" if totaal_acties else "0%")
col3.metric("Verdedigende Acties", verdedig_acties, f"{round(verdedig_acties/totaal_acties*100)}%" if totaal_acties else "0%")
col4.metric("Totaal Kansen", scoringskansen)

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Functies & Taken", "⏱️ Tijdlijn & Verloop", "📄 Ruwe Data"])

with tab1:
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("Verdeling Teamfuncties")
        fig_func = px.pie(df, names="functie", color="functie", color_discrete_map={"Aanvallen": "#27ae60", "Verdedigen": "#c0392b"}, hole=0.4)
        st.plotly_chart(fig_func, use_container_width=True)
    with col_right:
        st.subheader("Aantal gebeurtenissen per Teamtaak")
        fig_taak = px.bar(df, x="taak", color="functie", color_discrete_map={"Aanvallen": "#27ae60", "Verdedigen": "#c0392b"}, barmode="group")
        st.plotly_chart(fig_taak, use_container_width=True)

    st.subheader("Gedetailleerde Gebeurtenissen per Taak")
    fig_event = px.bar(df, y="event", color="taak", orientation="h")
    fig_event.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
    st.plotly_chart(fig_event, use_container_width=True)

with tab2:
    st.subheader("⏱️ Tijdsaanduiding & Verloop van de Wedstrijd")
    periodes = sorted(df["periode"].unique())
    selected_p = st.selectbox("Selecteer Periode voor Tijdlijn:", ["Alle Periodes"] + [f"Periode {p}" for p in periodes])

    df_p = df.copy()
    if selected_p != "Alle Periodes":
        df_p = df_p[df_p["periode"] == int(selected_p.split(" ")[1])]

    df_p = df_p.sort_values(by="minuut_float")

    st.markdown("##### 📈 Opbouw van de acties (Cumulatief over tijd)")
    df_p["teller"] = 1
    df_p["cumulatief"] = df_p.groupby("functie")["teller"].cumsum()
    fig_cum = px.line(df_p, x="minuut_float", y="cumulatief", color="functie", markers=True, color_discrete_map={"Aanvallen": "#27ae60", "Verdedigen": "#c0392b"})
    st.plotly_chart(fig_cum, use_container_width=True)

    st.markdown("##### 📊 Intensiteit per 5 Speelminuten")
    bin_size = 5
    df_p["tijdsblok"] = (df_p["minuut_int"] // bin_size) * bin_size
    df_p["tijdsblok_label"] = df_p["tijdsblok"].apply(lambda x: f"{x}-{x+bin_size} min")
    df_block = df_p.groupby(["tijdsblok", "tijdsblok_label", "functie"]).size().reset_index(name="aantal")
    fig_block = px.bar(df_block, x="tijdsblok_label", y="aantal", color="functie", barmode="group", color_discrete_map={"Aanvallen": "#27ae60", "Verdedigen": "#c0392b"})
    st.plotly_chart(fig_block, use_container_width=True)

with tab3:
    st.subheader("Alle Vastgelegde Gebeurtenissen")
    st.dataframe(df[["periode", "tijd", "minuut_float", "functie", "taak", "event"]], use_container_width=True)
    st.download_button("📥 Download deze data als CSV", df.to_csv(index=False).encode('utf-8'), "export.csv", "text/csv")
