"""GeoInsight AI — interface identique à la maquette (design Modernist, bleu Québec).

La maquette complète (app/maquette.html) est affichée en pleine page.
Les limites des régions sont injectées depuis data/regions_mrnf_cache.geojson
(mis à jour depuis le service MRNF quand il répond), donc la carte fonctionne
même si le réseau bloque le serveur du gouvernement.
L'ancienne interface est conservée dans app/main_ancien.py.
"""
import json
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
CACHE = ROOT / "data" / "regions_mrnf_cache.geojson"
QUARTIERS = ROOT / "data" / "quartiers_quebec.geojson"
SERVICE_REGIONS = ("https://servicescarto.mern.gouv.qc.ca/pes/rest/services/"
                   "Territoire/SDA_WMS/MapServer/0/query")

st.set_page_config(page_title="GeoInsight AI", layout="wide", initial_sidebar_state="collapsed")

# Masque toute l'interface Streamlit : seule la maquette est visible.
st.markdown("""
<style>
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
[data-testid="collapsedControl"], footer, #MainMenu {display:none !important;}
.block-container, [data-testid="stMainBlockContainer"] {padding:0 !important; max-width:100% !important;}
[data-testid="stAppViewContainer"], .stApp {background:#f3f2f2;}
[data-testid="stVerticalBlock"] {gap:0 !important;}
iframe {display:block; width:100% !important; height:100vh !important; border:0 !important;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=86400, show_spinner="Chargement des limites des régions…")
def charger_geojson():
    try:
        r = requests.get(SERVICE_REGIONS, params={
            "where": "1=1", "outFields": "RES_CO_REG,RES_NM_REG,RES_VA_SUP",
            "outSR": 4326, "returnGeometry": "true", "f": "geojson",
            "geometryPrecision": 5, "maxAllowableOffset": 0.002,
        }, timeout=20, headers={"User-Agent": "GeoInsight-AI/1.0"})
        r.raise_for_status()
        data = r.json()
        if data.get("type") == "FeatureCollection" and data.get("features"):
            CACHE.write_text(json.dumps(data), encoding="utf-8")
            return json.dumps(data)
    except (requests.RequestException, ValueError):
        pass
    return CACHE.read_text(encoding="utf-8")


@st.cache_data(show_spinner=False)
def construire_page(geojson):
    carte = (APP / "carte-quebec.html").read_text(encoding="utf-8")
    quartiers = QUARTIERS.read_text(encoding="utf-8") if QUARTIERS.exists() else "null"
    carte = carte.replace("<head>", "<head><script>window.__GEOJSON=" + geojson
                          + ";window.__QUARTIERS=" + quartiers + ";</script>", 1)
    carte3d = (APP / "carte-3d.html").read_text(encoding="utf-8")
    carte3d = carte3d.replace("<head>", "<head><script>window.__GEOJSON=" + geojson + ";</script>", 1)
    cle = ""
    try:
        # La clé est envoyée au navigateur : n'activer que sur une application privée.
        if st.secrets.get("COPILOT_ACTIF", False):
            cle = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        cle = ""
    injection = ("<script>window.__CARTE_HTML="
                 + json.dumps(carte).replace("</", "<\\/")
                 + ";window.__CARTE3D_HTML=" + json.dumps(carte3d).replace("</", "<\\/")
                 + ";window.__ANTHROPIC_KEY=" + json.dumps(cle) + ";</script>")
    page = (APP / "maquette.html").read_text(encoding="utf-8")
    return page.replace("<head>", "<head>" + injection, 1)


components.html(construire_page(charger_geojson()), height=1000, scrolling=True)
