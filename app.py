import os
import json
import base64
import urllib.parse
import urllib.request
import glob
import pandas as pd
import plotly.express as px
import streamlit as st

APP_VERSION = "2.7.0"

# --- CONFIGURATIE (Pas dit aan naar jouw server en Streamlit Cloud URLs) ---
SERVER_PHP_URL = "https://jouw-domein.nl/get_matches.php"
SERVER_DATA_BASE_URL = "https://jouw-domein.nl/data/"
STREAMLIT_CLOUD_URL = "https://voetbalobservatietool-supifuf6eqyrufsb9vdbch.streamlit.app"

st.set_page_config(
    page_title=f"Voetbal Observatie Dashboard v{APP_VERSION}",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Voetbal Observatie Dashboard")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
match_data = None
selected_filename = None

# --- HULPFUNCTIE VOOR SCHONE DEEL-URLS ---
@st.cache_data(show_spinner=False)
def get_clean_share_url(base_app_url, filename=None, encoded_data=None):
    clean_base = base_app_url.rstrip('/')

    # 1. Schone URL op basis van de bestandsnaam op de server
    if filename:
        return f"{clean_base}/?match={filename}"

    # 2. Privacy-vriendelijke verkorter via is.gd als fallback bij ruwe URL-data
    if encoded_data:
        long_url = f"{clean_base}/?data={encoded_data}"
        try:
            api_url = f"https://is.gd/create.php?format=simple&url={urllib.parse.quote(long_url)}"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return resp.read().decode('utf-8')
        except:
            pass
        return long_url

    return clean_base

# --- 1. DIRECTE DATA VIA URL PARAMETER ---
query_params = st.query_params
encoded_data = query_params.get("data", None)

if encoded_data:
    try:
        decoded_bytes = base64.b64decode(urllib.parse.unquote(encoded_data))
        match_data = json.loads(decoded_bytes.decode("utf-8"))
        st.success("⚡ Wedstrijd direct geladen vanuit de observatietool!")
    except Exception as e:
        st.error(f"Fout bij het uitlezen van URL data: {e}")

# --- 2. SELECTIE EN OPHALEN VAN WEDSTRIJDEN ---
if not match_data:
    st.sidebar.header("🔍 Wedstrijd Selectie")

    matches_list = []

    # Optie A: Lokale /data/ map (Desktop modus)
    if os.path.exists(DATA_DIR):
        local_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), key=os.path.getmtime, reverse=True)
        for f_path in local_files:
            fname = os.path.basename(f_path)
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
            matches_list.append({"filename": fname, "label": label, "source": "local"})

    # Optie B: Ophalen via get_matches.php server (Cloud / Remote modus)
    if not matches_list and SERVER_PHP_URL:
        try:
            req = urllib.request.Request(SERVER_PHP_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    server_json = json.loads(response.read().decode('utf-8'))
                    for item in server_json:
                        datum_raw = item.get("datum", "")
                        if datum_raw and "T" in datum_raw:
                            d_part, t_part = datum_raw.split("T")
                            jaar, maand, dag = d_part.split("-")
                            tijd_str = t_part[:5]
                            datum_formatted = f"{dag}-{maand}-{jaar} {tijd_str}"
                        else:
                            datum_formatted = item.get("label", item["filename"])

                        wij = item.get("wij", "Wij")
                        zij = item.get("zij", "Zij")

                        matches_list.append({
                            "filename": item["filename"],
                            "label": f"{wij} vs {zij} ({datum_formatted})",
                            "source": "server"
                        })
        except Exception as e:
            st.sidebar.warning("⚠️ Kon geen verbinding maken met get_matches.php op de server.")

    # Weergave in de sidebar dropdown
    if matches_list:
        labels = [m["label"] for m in matches_list]
        requested_match = query_params.get("match", None)

        default_idx = 0
        if requested_match:
            for idx, m in enumerate(matches_list):
                if m["filename"] == requested_match:
                    default_idx = idx
                    break

        selected_label = st.sidebar.selectbox("Kies een opgeslagen wedstrijd:", labels, index=default_idx)
        selected_match_info = matches_list[labels.index(selected_label)]
        selected_filename = selected_match_info["filename"]

        # Laden van het gekozen JSON-bestand
        if selected_match_info["source"] == "local":
            with open(os.path.join(DATA_DIR, selected_filename), "r", encoding="utf-8") as f:
                match_data = json.load(f)
        else:
            file_url = SERVER_DATA_BASE_URL + selected_filename
            req = urllib.request.Request(file_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(file_url) as resp:
                match_data = json.loads(resp.read().decode('utf-8'))
    else:
        uploaded_file = st.sidebar.file_uploader("Upload handmatig een JSON wedstrijd-bestand:", type=["json"])
        if uploaded_file:
            match_data = json.load(uploaded_file)

# --- 3. DELEN FUNCTIONALITEIT (CLEAN URL & QR-CODE) ---
if selected_filename or encoded_data:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔗 Dashboard Delen")

    share_url = get_clean_share_url(STREAMLIT_CLOUD_URL, selected_filename, encoded_data)

    st.sidebar.caption("Kopieer deze link om dit specifieke dashboard te delen:")
    st.sidebar.code(share_url, language=None)

    qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(share_url)}"
    with st.sidebar.popover("📱 Toon QR-Code om te scannen"):
        st.image(qr_api_url, caption="Scan met telefooncamera om te openen", width=150)

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
