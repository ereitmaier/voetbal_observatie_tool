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
from reportlab.graphics.shapes import Drawing, String, Line, PolyLine, Rect
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

APP_VERSION = "4.0.0"

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

tab1, tab2, tab3 = st.tabs(["📊 Functies & Taken", "⏱️ Tijdlijn & Verloop", "📄 Ruwe Data & PDF"])

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

        fig_matrix.update_traces(marker=dict(symbol="square"), opacity=0.9)
        fig_matrix.update_layout(
            height=380,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(dtick=bin_minutes, showgrid=True, gridcolor="#2c3e50", zeroline=False),
            yaxis=dict(showgrid=True, gridcolor="#2c3e50", autorange="reversed"),
            legend=dict(title="Impactwaarde", orientation="v")
        )

        st.plotly_chart(fig_matrix, use_container_width=True)

    st.markdown("---")
    st.markdown("##### 📉 Wedstrijdmomentum & Cumulatieve Impact Score")

    for p in periodes:
        df_p = df[df["periode"] == p].copy().sort_values(by="minuut_float")
        if df_p.empty: continue

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
            title=f"Wedstrijddynamiek Periode {p} (Positief = Overwicht, Negatief = Onder Druk)"
        )

        fig_momentum.add_hline(y=0, line_dash="dash", line_color="#7f8c8d")
        fig_momentum.update_traces(line_color="#2ecc71", fillcolor="rgba(46, 204, 113, 0.2)")
        fig_momentum.update_layout(
            height=320,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(showgrid=True, gridcolor="#2c3e50"),
            yaxis=dict(showgrid=True, gridcolor="#2c3e50")
        )

        st.plotly_chart(fig_momentum, use_container_width=True)

# --- FUNCTIE VOOR COMPLEET PDF RAPPORT MET VECTOR TIJDGRAFIEKEN ---
def generate_pdf_report(df, wedstrijd_info):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor("#181825"), spaceAfter=6)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor("#7f8c8d"), spaceAfter=15)
    section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=13, textColor=colors.HexColor("#27ae60"), spaceBefore=14, spaceAfter=8)
    hdr_style = ParagraphStyle('HdrStyle', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.white)
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor("#2c3e50"))
    cell_center = ParagraphStyle('CellCenter', parent=cell_style, alignment=1)

    wij = wedstrijd_info.get('wij', 'Wij')
    zij = wedstrijd_info.get('zij', 'Zij')
    datum_str = pd.Timestamp.now().strftime('%d-%m-%Y %H:%M')

    # 1. Header
    story.append(Paragraph(f"⚽ Wedstrijdrapport: {wij} vs {zij}", title_style))
    story.append(Paragraph(f"Gegenereerd op: {datum_str} | Observatietool v{APP_VERSION}", subtitle_style))
    story.append(Spacer(1, 5))

    # 2. Kernstatistieken Tabel
    story.append(Paragraph("📊 Wedstrijdsamenvatting", section_style))
    data_stats = [
        [Paragraph("Statistiek", hdr_style), Paragraph("Waarde", hdr_style)],
        [Paragraph("Einduitslag", cell_style), Paragraph(f"<b>{goals_wij} - {goals_zij}</b>", cell_style)],
        [Paragraph("Totaal Aantal Acties", cell_style), Paragraph(str(totaal_acties), cell_style)],
        [Paragraph("Aanvallende Acties", cell_style), Paragraph(f"{aanval_acties} ({round(aanval_acties/totaal_acties*100) if totaal_acties else 0}%)", cell_style)],
        [Paragraph("Verdedigende Acties", cell_style), Paragraph(f"{verdedig_acties} ({round(verdedig_acties/totaal_acties*100) if totaal_acties else 0}%)", cell_style)],
        [Paragraph("Totaal Kansen", cell_style), Paragraph(str(scoringskansen), cell_style)]
    ]
    t_stats = Table(data_stats, colWidths=[200, 280])
    t_stats.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), colors.HexColor("#242438")),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#bdc3c7")),
    ]))
    story.append(t_stats)
    story.append(Spacer(1, 10))

    # 3. Vector Grafiek 1: Cirkeldiagram Teamfuncties
    story.append(Paragraph("📈 Verdeling Teamfuncties", section_style))
    d_pie = Drawing(480, 150)
    pc = Pie()
    pc.x = 140
    pc.y = 10
    pc.width = 130
    pc.height = 130
    pc.data = [aanval_acties if aanval_acties else 1, verdedig_acties if verdedig_acties else 1]
    pc.labels = [f'Aanvallen ({aanval_acties})', f'Verdedigen ({verdedig_acties})']
    pc.slices[0].fillColor = colors.HexColor("#27ae60")
    pc.slices[1].fillColor = colors.HexColor("#c0392b")
    d_pie.add(pc)
    story.append(d_pie)
    story.append(Spacer(1, 10))

    # 4. Vector Grafiek 2: Staafdiagram Aantal Acties per Teamtaak
    story.append(Paragraph("📊 Aantal Gebeurtenissen per Teamtaak", section_style))
    df_taak_counts = df.groupby("taak").size().reset_index(name="aantal")
    taken = df_taak_counts["taak"].tolist()
    aantallen = df_taak_counts["aantal"].tolist()

    if taken and aantallen:
        d_bar = Drawing(480, 150)
        bc = VerticalBarChart()
        bc.x = 40
        bc.y = 25
        bc.height = 110
        bc.width = 400
        bc.data = [aantallen]
        bc.categoryAxis.categoryNames = [t[:18] + '...' if len(t) > 18 else t for t in taken]
        bc.categoryAxis.labels.fontSize = 8
        bc.categoryAxis.labels.dy = -10
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = max(aantallen) + 2
        bc.bars[0].fillColor = colors.HexColor("#3498db")
        d_bar.add(bc)
        story.append(d_bar)
        story.append(Spacer(1, 15))

    # 5. VECTOR GRAFIEK 3: WEDSTRIJDMOMENTUM & TIJDLIN (LIJNGRAFIEK)
    story.append(Paragraph("⏱️ Wedstrijdmomentum Over Tijd (Cumulatieve Impact)", section_style))

    periodes = sorted(df["periode"].unique())
    for p in periodes:
        df_p = df[df["periode"] == p].copy().sort_values(by="minuut_float")
        if df_p.empty: continue

        df_p["cumulatieve_impact"] = df_p["waarde"].cumsum()

        times = df_p["minuut_float"].tolist()
        scores = df_p["cumulatieve_impact"].tolist()

        d_line = Drawing(480, 140)

        # Bepaal schaal
        min_x, max_x = 0, max(max(times) if times else 45, 45)
        min_y = min(min(scores) if scores else 0, -2)
        max_y = max(max(scores) if scores else 0, 2)

        margin_l, margin_r, margin_t, margin_b = 40, 20, 20, 25
        w_graph = 480 - margin_l - margin_r
        h_graph = 140 - margin_t - margin_b

        # Nul-lijn (Referentielijn)
        y_zero = margin_b + (0 - min_y) / (max_y - min_y if max_y != min_y else 1) * h_graph
        d_line.add(Line(margin_l, y_zero, margin_l + w_graph, y_zero, strokeColor=colors.HexColor("#7f8c8d"), strokeWidth=1, strokeDashArray=[2,2]))

        # Punten omzetten naar PDF-coördinaten
        points = []
        for x, y in zip(times, scores):
            px_val = margin_l + (x - min_x) / (max_x - min_x) * w_graph
            py_val = margin_b + (y - min_y) / (max_y - min_y if max_y != min_y else 1) * h_graph
            points.append((px_val, py_val))

        # Lijn tekenen
        if len(points) > 1:
            flat_points = [coord for pt in points for coord in pt]
            d_line.add(PolyLine(flat_points, strokeColor=colors.HexColor("#2ecc71"), strokeWidth=2))

        # Punten (stippen) markeren
        for px_val, py_val in points:
            d_line.add(Rect(px_val - 2, py_val - 2, 4, 4, fillColor=colors.HexColor("#27ae60"), strokeColor=None))

        # Assen & Labels
        d_line.add(String(margin_l - 25, y_zero - 3, "0", fontSize=8, fillColor=colors.HexColor("#7f8c8d")))
        d_line.add(String(margin_l, 8, f"Periode {p} (0 - {int(max_x)} min)", fontSize=8, fillColor=colors.HexColor("#2c3e50")))

        story.append(d_line)
        story.append(Spacer(1, 10))

    # 6. Gebeurtenissen per Taak & Impactwaarde Tabel
    story.append(Paragraph("📋 Gedetailleerd Gebeurtenissen Overzicht", section_style))
    df_summary = df.groupby(["taak", "event", "waarde_str", "waarde"]).size().reset_index(name="aantal")
    df_summary = df_summary.sort_values(by="waarde", ascending=True)

    table_data = [[
        Paragraph("Teamtaak", hdr_style),
        Paragraph("Gebeurtenis", hdr_style),
        Paragraph("Impact", hdr_style),
        Paragraph("Aantal", hdr_style)
    ]]

    for _, row in df_summary.iterrows():
        w_val = str(row["waarde_str"])
        hex_color = COLOR_MAP_WAARDE.get(w_val, "#7f8c8d")

        impact_p = Paragraph(f"<font color='{hex_color}'><b>{w_val}</b></font>", cell_center)

        table_data.append([
            Paragraph(str(row["taak"]), cell_style),
            Paragraph(str(row["event"]), cell_style),
            impact_p,
            Paragraph(str(row["aantal"]), cell_center)
        ])

    t_summary = Table(table_data, colWidths=[140, 220, 60, 60])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#242438")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#bdc3c7")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_summary)

    doc.build(story)
    buffer.seek(0)
    return buffer

with tab3:
    st.subheader("📥 Exporteer Wedstrijdrapport & Data")

    col_pdf, col_csv = st.columns(2)

    with col_pdf:
        st.markdown("##### 📄 PDF Wedstrijdrapport")
        st.caption("Genereer een printbaar PDF document met samenvatting, functieverdeling, tijdsverloop en gebeurtenissen.")
        try:
            pdf_data = generate_pdf_report(df, wedstrijd_info)
            st.download_button(
                label="📄 Download PDF Rapport (Met Alle Grafieken)",
                data=pdf_data,
                file_name=f"Wedstrijdrapport_{team_wij_naam}_vs_{team_zij_naam}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"Fout bij genereren PDF: {e}")

    with col_csv:
        st.markdown("##### 📊 Ruwe Data CSV")
        st.caption("Exporteer alle geobserveerde acties naar een CSV bestand voor Excel.")
        st.download_button(
            label="📥 Download Ruwe Data (CSV)",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name=f"observatie_{team_wij_naam}_vs_{team_zij_naam}.csv",
            mime="text/csv"
        )

    st.markdown("---")
    st.subheader("📋 Alle Vastgelegde Gebeurtenissen")
    st.dataframe(df[["periode", "tijd", "minuut_float", "functie", "taak", "event", "waarde"]], use_container_width=True)
