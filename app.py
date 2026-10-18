import os
import json
import urllib.parse
import urllib.request
import glob
import pandas as pd
import plotly.express as px
import streamlit as st

APP_VERSION = "3.2.0"

# --- CONFIGURATIE ---
SERVER_PHP_URL = "https://team-level-up.com/otsv/get_matches.php"
SERVER_DATA_BASE_URL = "https://team-level-up.com/otsv/data/"
STREAMLIT_CLOUD_URL = "https://voetbalobservatietool-supifuf6eqyrufsb9vdbch.streamlit.app"

# Fallback mapping voor eerdere JSON-bestanden zonder 'waarde'
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

# Discrete kleurenschaal: Rood (-3) via Oranje (0) naar Groen (+3)
COLOR_MAP_WAARDE = {
    "-3": "#c0392b",  # Donkerrood (Tegendoelpunt)
    "-2": "#e74c3c",  # Rood (Groot balverlies)
    "-1": "#e67e22",  # Rood-Oranje (Balverlies)
     "0": "#f39c12",  # Oranje (Neutraal)
    "+1": "#f1c40f",  # Geel / Amber (Licht positief)
    "+2": "#2ecc71",  # Lichtgroen / Lime (Kans / Redding)
    "+3": "#27ae60"   # Donkergroen (Doelpunt)
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
                st.error("❌ Ongeldige of niet-bestaande link-token.")
    except Exception as e:
        st.error(f"Fout bij het ophalen van beveiligde data via token: {e}")

# --- 2. LOKALE BEHEERDER MODUS (ZICHTBAAR WANNEER ER GEEN TOKEN IS) ---
if not match_data:
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
            matches_list.append({"filename": fname, "label": label, "source": "local"})

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

    if matches_list:
        labels = [m["label"] for m in matches_list]
        selected_label = st.sidebar.selectbox("Kies een opgeslagen wedstrijd:", labels)
        selected_match_info = matches_list[labels.index(selected_label)]
        selected_filename = selected_match_info["filename"]

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

# --- 3. DELEN FUNCTIONALITEIT ---
if match_data:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔗 Dashboard Delen")

    if not current_token and selected_filename:
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
    elif selected_filename:
        share_url = f"{STREAMLIT_CLOUD_URL}/?match={selected_filename}"
    else:
        share_url = STREAMLIT_CLOUD_URL

    st.sidebar.caption("Kopieer deze link om dit specifieke dashboard te delen:")
    st.sidebar.code(share_url, language=None)

    qr_api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(share_url)}"
    with st.sidebar.popover("📱 Toon QR-Code om te scannen"):
        st.image(qr_api_url, caption="Scan met telefooncamera om te openen", width=150)

if not match_data:
    st.info("👋 Welkom! Gebruik een geldige token-link of kies lokaal een wedstrijd in het menu.")
    st.sidebar.markdown("---")
    st.sidebar.caption(f"App Versie: **v{APP_VERSION}**")
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

# Ken de numerieke én geformatteerde string-waarde toe
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
        fig_func = px.pie(
            df,
            names="functie",
            color="functie",
            color_discrete_map={"Aanvallen": "#27ae60", "Verdedigen": "#c0392b"},
            hole=0.4
        )
        st.plotly_chart(fig_func, use_container_width=True)

    with col_right:
        st.subheader("Aantal gebeurtenissen per Teamtaak")
        fig_taak = px.bar(
            df,
            x="taak",
            color="functie",
            color_discrete_map={"Aanvallen": "#27ae60", "Verdedigen": "#c0392b"},
            barmode="group"
        )
        st.plotly_chart(fig_taak, use_container_width=True)

    # --- GEDETAILLEERDE GEBEURTENISSEN DISCREET GEKLEURD VAN ROOD (-3) NAAR GROEN (+3) ---
    st.subheader("Gedetailleerde Gebeurtenissen per Taak")

    df_events_count = df.groupby(["event", "taak", "waarde_str"]).size().reset_index(name="aantal")

    fig_event = px.bar(
        df_events_count,
        y="event",
        x="aantal",
        color="waarde_str",
        orientation="h",
        color_discrete_map=COLOR_MAP_WAARDE,
        category_orders={"waarde_str": ["-3", "-2", "-1", "0", "+1", "+2", "+3"]},
        hover_data={"waarde_str": True, "taak": True, "aantal": True},
        labels={
            "event": "Gebeurtenis",
            "aantal": "Aantal keer voorgekomen",
            "waarde_str": "Impactwaarde",
            "taak": "Teamtaak"
        }
    )

    fig_event.update_layout(
        yaxis={'categoryorder': 'total ascending'},
        height=450,
        xaxis=dict(showgrid=True, gridcolor="#2c3e50"),
        legend=dict(title="Impactwaarde", orientation="v")
    )

    st.plotly_chart(fig_event, use_container_width=True)

with tab2:
    st.subheader("⏱️ Tijdsaanduiding & Verloop van de Wedstrijd")

    periodes = sorted(df["periode"].unique())

    # --- 1. MATRIX GRAFIEK MET ROOD-NAAR-GROEN KLEURENSCHEMA ---
    st.markdown("##### 🟩 Gebeurtenissen per Tijdsinterval Matrix")

    col_interval, col_groep = st.columns([1, 2])
    with col_interval:
        bin_minutes = st.select_slider(
            "Kies tijdsinterval (minuten):",
            options=[1, 5, 10, 15],
            value=5
        )
    with col_groep:
        y_as_keuze = st.radio(
            "Groepeer y-as op:",
            options=["event", "taak"],
            format_func=lambda x: "Specifieke Gebeurtenis (Event)" if x == "event" else "Teamtaak",
            horizontal=True
        )

    for p in periodes:
        st.markdown(f"###### 📍 Periode {p}")
        df_p = df[df["periode"] == p].copy().sort_values(by="minuut_float")

        if df_p.empty:
            st.info(f"Geen gebeurtenissen vastgelegd in Periode {p}.")
            continue

        df_p["tijdsblok_start"] = (df_p["minuut_int"] // bin_minutes) * bin_minutes
        df_p["tijdsblok_label"] = df_p["tijdsblok_start"].apply(lambda x: f"{x}-{x+bin_minutes}m")

        df_matrix = df_p.groupby(["tijdsblok_start", "tijdsblok_label", y_as_keuze, "waarde_str"]).size().reset_index(name="aantal")

        fig_matrix = px.scatter(
            df_matrix,
            x="tijdsblok_start",
            y=y_as_keuze,
            color="waarde_str",
            size="aantal",
            size_max=14,
            color_discrete_map=COLOR_MAP_WAARDE,
            category_orders={"waarde_str": ["-3", "-2", "-1", "0", "+1", "+2", "+3"]},
            hover_data={"aantal": True, "tijdsblok_label": True, "waarde_str": True, "tijdsblok_start": False},
            labels={
                y_as_keuze: "Gebeurtenis / Taak" if y_as_keuze == "event" else "Teamtaak",
                "tijdsblok_start": f"Speelminuut (Periode {p})",
                "waarde_str": "Impactwaarde",
                "aantal": "Aantal acties"
            },
            title=f"Uitvoering van acties over tijd — Periode {p} (Interval: per {bin_minutes} min)"
        )

        fig_matrix.update_traces(
            marker=dict(symbol="square"),
            opacity=0.9
        )

        fig_matrix.update_layout(
            height=380,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(dtick=bin_minutes, showgrid=True, gridcolor="#2c3e50", zeroline=False),
            yaxis=dict(showgrid=True, gridcolor="#2c3e50", autorange="reversed"),
            legend=dict(title="Impactwaarde", orientation="v")
        )

        st.plotly_chart(fig_matrix, use_container_width=True)

    # --- 2. WEDSTRIJDMOMENTUM & CUMULATIEVE IMPACT ---
    st.markdown("---")
    st.markdown("##### 📉 Wedstrijdmomentum & Cumulatieve Impact Score")

    for p in periodes:
        df_p = df[df["periode"] == p].copy().sort_values(by="minuut_float")
        if df_p.empty:
            continue

        df_p["cumulatieve_impact"] = df_p["waarde"].cumsum()

        fig_momentum = px.area(
            df_p,
            x="minuut_float",
            y="cumulatieve_impact",
            markers=True,
            hover_data={"tijd": True, "event": True, "waarde": True, "cumulatieve_impact": True},
            labels={
                "minuut_float": f"Speelminuut (Periode {p})",
                "cumulatieve_impact": "Cumulatieve Score",
                "waarde": "Impactwaarde",
                "event": "Gebeurtenis"
            },
            title=f"Wedstrijddynamiek Periode {p} (Positief = Overwicht Zaandijk, Negatief = Onder Druk)"
        )

        fig_momentum.add_hline(y=0, line_dash="dash", line_color="#7f8c8d")

        fig_momentum.update_traces(
            line_color="#2ecc71",
            fillcolor="rgba(46, 204, 113, 0.2)"
        )

        fig_momentum.update_layout(
            height=320,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(showgrid=True, gridcolor="#2c3e50"),
            yaxis=dict(showgrid=True, gridcolor="#2c3e50")
        )

        st.plotly_chart(fig_momentum, use_container_width=True)

with tab3:
    st.subheader("Alle Vastgelegde Gebeurtenissen")
    st.dataframe(df[["periode", "tijd", "minuut_float", "functie", "taak", "event", "waarde"]], use_container_width=True)
    st.download_button("📥 Download deze data als CSV", df.to_csv(index=False).encode('utf-8'), "export.csv", "text/csv")
