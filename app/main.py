"""GeoInsight AI — plateforme géospatiale extensible, pilote initial à Québec."""
from pathlib import Path
import sys
import json
import unicodedata
import requests

import folium
import pandas as pd
import streamlit as st
from pyproj import Geod
from shapely.geometry import shape, mapping
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
GEOJSON = ROOT / "data" / "quartiers.geojson"
CSV = ROOT / "data" / "indicateurs_quartiers.csv"
GEOD = Geod(ellps="WGS84")

st.set_page_config(page_title="GeoInsight AI | Intelligence territoriale", page_icon="🌎", layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.2rem;max-width:1500px}
div[data-testid="stMetric"]{background:#f0f7f8;border:1px solid #d5e8ea;border-radius:12px;padding:16px}
</style>""", unsafe_allow_html=True)

def normaliser(value):
    value = unicodedata.normalize("NFKD", str(value).strip().casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch))

@st.cache_data(show_spinner=False)
def charger_quartiers(path, mtime):
    with open(path, encoding="utf-8") as fp:
        collection = json.load(fp)
    if collection.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON attendu : FeatureCollection.")
    rows = []
    for feature in collection.get("features", []):
        nom = str((feature.get("properties") or {}).get("NOM", "")).strip()
        geometry = feature.get("geometry")
        if not nom or not geometry:
            continue
        geom = shape(geometry)
        if geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        superficie_m2, _ = GEOD.geometry_area_perimeter(geom)
        rows.append({"quartier": nom, "superficie_km2": abs(superficie_m2) / 1e6,
                     "geometry": geometry})
    if not rows:
        raise ValueError("Aucune géométrie de quartier valide.")
    return rows

def charger_indicateurs(source):
    df = pd.read_csv(source, encoding="utf-8-sig")
    required = {"quartier", "source", "annee"}
    if not required.issubset(df.columns):
        raise ValueError("Colonnes obligatoires : quartier, source, annee")
    if df[["quartier", "source", "annee"]].isna().any().any():
        raise ValueError("Valeurs obligatoires manquantes dans le CSV.")
    df["key"] = df["quartier"].map(normaliser)
    if df["key"].duplicated().any():
        raise ValueError("Plusieurs lignes pour un même quartier.")
    for field in ("population", "revenu_median"):
        if field in df:
            df[field] = pd.to_numeric(df[field], errors="coerce")
            if (df[field].dropna() < 0).any():
                raise ValueError("Valeur négative : " + field)
    return df

SERVICE_REGIONS = ("https://servicescarto.mern.gouv.qc.ca/pes/rest/services/"
                   "Territoire/SDA_WMS/MapServer/0/query")

@st.cache_data(ttl=86400, show_spinner="Chargement des limites officielles…")
def charger_regions():
    response = requests.get(SERVICE_REGIONS, params={
        "where": "1=1",
        "outFields": "RES_CO_REG,RES_NM_REG,RES_VA_SUP",
        "outSR": 4326,
        "returnGeometry": "true",
        "f": "geojson",
        "geometryPrecision": 5,
        "maxAllowableOffset": 0.002
    }, timeout=90)
    response.raise_for_status()
    payload = response.json()
    if payload.get("type") != "FeatureCollection" or not payload.get("features"):
        raise ValueError("Le service officiel n'a pas renvoyé de régions GeoJSON.")
    regions = []
    codes = set()
    for feature in payload["features"]:
        props = feature.get("properties") or {}
        code = str(props.get("RES_CO_REG") or "").strip().zfill(2)
        name = str(props.get("RES_NM_REG") or "").strip()
        geom = feature.get("geometry")
        if not name or not geom:
            continue
        polygon = shape(geom)
        if polygon.is_empty:
            continue
        if code in codes:
            raise ValueError("Codes régionaux dupliqués dans le service.")
        codes.add(code)
        # Simplification pour limiter le volume transféré au navigateur.
        feature["geometry"] = mapping(polygon.simplify(0.006, preserve_topology=True))
        feature["properties"] = {"code": code, "nom": name}
        regions.append(feature)
    if len(regions) != 17:
        raise ValueError(f"Nombre de régions inattendu : {len(regions)} (17 attendues).")
    return regions

with st.sidebar:
    st.markdown("### 🗺️ Échelle d’exploration")
    vue = st.radio("Vue", ["Québec — régions", "Ville de Québec — quartiers"], index=0)

if vue == "Québec — régions":
    st.title("🌎 GeoInsight AI — Province de Québec")
    st.caption("Limites officielles des 17 régions administratives")
    try:
        regions = charger_regions()
    except (requests.RequestException, ValueError, TypeError) as error:
        st.error("Impossible de charger les limites officielles pour le moment.")
        st.caption(str(error))
        st.stop()

    regions.sort(key=lambda f: f["properties"]["code"])
    options = ["Toutes les régions"] + [
        f'{r["properties"]["code"]} — {r["properties"]["nom"]}' for r in regions
    ]
    choix = st.selectbox("Région administrative", options)
    visibles = regions if choix == "Toutes les régions" else [
        r for r in regions
        if f'{r["properties"]["code"]} — {r["properties"]["nom"]}' == choix
    ]
    c1, c2 = st.columns(2)
    c1.metric("Régions du Québec", len(regions))
    c2.metric("Régions affichées", len(visibles))
    carte = folium.Map(location=[51.2, -71.4], zoom_start=5,
                       tiles="OpenStreetMap", control_scale=True)
    folium.GeoJson(
        {"type": "FeatureCollection", "features": visibles},
        name="Régions administratives",
        tooltip=folium.GeoJsonTooltip(fields=["code", "nom"], aliases=["Code :", "Région :"]),
        style_function=lambda _: {"color": "#087f8c", "weight": 1.7,
                                  "fillColor": "#21a0a6", "fillOpacity": 0.16},
        highlight_function=lambda _: {"color": "#ff9d2e", "weight": 3,
                                      "fillOpacity": 0.36},
    ).add_to(carte)
    polygons = [shape(f["geometry"]).bounds for f in visibles]
    carte.fit_bounds([[min(b[1] for b in polygons), min(b[0] for b in polygons)],
                      [max(b[3] for b in polygons), max(b[2] for b in polygons)]])
    folium.LayerControl().add_to(carte)
    st_folium(carte, height=650, use_container_width=True, returned_objects=[])
    st.caption("Source : Gouvernement du Québec, MRNF — Découpages administratifs, "
               "service ArcGIS REST (simplification géométrique pour l'affichage).")
    st.info("Prochaine étape : MRC et municipalités. Les données de quartiers de Québec "
            "restent accessibles dans la deuxième vue.")
    st.stop()

st.title("🌎 GeoInsight AI")
st.caption("Plateforme de Business Intelligence géospatiale · Province de Québec")
st.caption("Couverture visée : ensemble de la province de Québec · Données actuellement chargées : quartiers de la ville de Québec")
if not GEOJSON.exists():
    try:
        from etl.ingest_quartiers import fetch_quartiers
        with st.spinner("Chargement initial des quartiers depuis Données Québec…"):
            geojson, _source_url = fetch_quartiers()
            GEOJSON.parent.mkdir(parents=True, exist_ok=True)
            GEOJSON.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")
    except Exception as error:
        st.error("Impossible de charger les quartiers depuis Données Québec. Réessaie ultérieurement.")
        st.caption(f"Détail technique : {error}")
        st.stop()
try:
    zones = charger_quartiers(str(GEOJSON), GEOJSON.stat().st_mtime)
except (OSError, ValueError, json.JSONDecodeError) as error:
    st.error(f"Erreur de chargement : {error}")
    st.stop()

territoires = pd.DataFrame([{"quartier": z["quartier"],
                              "superficie_km2": z["superficie_km2"]} for z in zones])
territoires["key"] = territoires["quartier"].map(normaliser)
if territoires["key"].duplicated().any():
    st.error("Les noms des quartiers ne sont pas uniques.")
    st.stop()
names = sorted(territoires["quartier"].tolist())

with st.sidebar:
    st.title("🧭 Exploration territoriale")
    st.selectbox("Couverture", ["Province de Québec — pilote actuel : ville de Québec"], help="Les données des autres municipalités seront intégrées progressivement.")
    selected = st.selectbox("Sélectionner un quartier", ["Tous les quartiers"] + names)
    show_borders = st.checkbox("Afficher les limites", value=True)
    st.divider()
    uploaded = st.file_uploader("Charger un CSV socioéconomique vérifié", type="csv")
    st.caption("Colonnes : quartier, source, annee; population et revenu_median facultatives.")

source = uploaded if uploaded is not None else CSV if CSV.exists() else None
socio = None
if source is not None:
    try:
        socio = charger_indicateurs(source)
    except (UnicodeError, ValueError, pd.errors.ParserError) as error:
        st.error(f"Le CSV n'a pas été intégré : {error}")

merged = territoires.copy()
if socio is not None:
    unmatched = socio.loc[~socio["key"].isin(territoires["key"]), "quartier"].tolist()
    if unmatched:
        st.warning(f"Quartiers non reconnus dans le CSV : {', '.join(unmatched[:6])}")
    merged = merged.merge(socio.drop(columns=["quartier"]), how="left",
                          on="key", validate="one_to_one")
    if "population" in merged:
        merged["densite_hab_km2"] = merged["population"] / merged["superficie_km2"].replace(0, float("nan"))
filtered = merged if selected == "Tous les quartiers" else merged[merged["quartier"] == selected]

tab_map, tab_analysis, tab_method = st.tabs(["🗺️ Carte", "📊 Analyses", "📚 Méthode"])
with tab_map:
    c1, c2, c3 = st.columns(3)
    c1.metric("Quartiers affichés", len(filtered))
    c2.metric("Superficie des polygones", f"{filtered['superficie_km2'].sum():.1f} km²")
    if "population" in filtered and filtered["population"].notna().all():
        c3.metric("Population", f"{filtered['population'].sum():,.0f}".replace(",", " "))
    else:
        c3.metric("Population", "Non disponible")
    selected_names = set(filtered["quartier"])
    visible = [z for z in zones if z["quartier"] in selected_names]
    m = folium.Map(location=[46.8139, -71.2080], zoom_start=11, tiles="OpenStreetMap",
                   control_scale=True)
    if show_borders:
        features = [{"type": "Feature", "properties": {"NOM": z["quartier"]},
                     "geometry": z["geometry"]} for z in visible]
        folium.GeoJson({"type": "FeatureCollection", "features": features},
                       name="Quartiers",
                       tooltip=folium.GeoJsonTooltip(fields=["NOM"], aliases=["Quartier :"]),
                       style_function=lambda _: {"color": "#087f8c", "weight": 2,
                                                   "fillColor": "#31b5b9", "fillOpacity": 0.22},
                       highlight_function=lambda _: {"color": "#fb923c", "weight": 3,
                                                       "fillOpacity": 0.4}).add_to(m)
    if selected != "Tous les quartiers" and visible:
        bounds = [shape(z["geometry"]).bounds for z in visible]
        m.fit_bounds([[min(x[1] for x in bounds), min(x[0] for x in bounds)],
                      [max(x[3] for x in bounds), max(x[2] for x in bounds)]])
    folium.LayerControl().add_to(m)
    st_folium(m, height=600, use_container_width=True, returned_objects=[])

with tab_analysis:
    st.subheader("Indicateurs territoriaux")
    if socio is None:
        st.info("Les superficies sont réelles. Importer des données fiables pour les indicateurs socioéconomiques.")
    fields = ["quartier", "superficie_km2"] + [
        k for k in ("population", "densite_hab_km2", "revenu_median", "annee", "source")
        if k in filtered.columns]
    st.dataframe(filtered[fields].sort_values("quartier"), use_container_width=True, hide_index=True)
    st.download_button("Exporter CSV", data=filtered[fields].to_csv(index=False).encode("utf-8-sig"),
                       file_name="geoinsight_quebec.csv", mime="text/csv")
    options = ["superficie_km2"] + [k for k in
        ("population", "densite_hab_km2", "revenu_median")
        if k in filtered and filtered[k].notna().any()]
    metric = st.selectbox("Comparer par indicateur", options)
    plot = filtered[["quartier", metric]].dropna().set_index("quartier").sort_values(metric, ascending=False)
    if not plot.empty:
        st.bar_chart(plot, horizontal=True)
    if socio is not None and "population" in merged:
        st.caption(f"Couverture population : {merged['population'].notna().sum()}/{len(merged)} quartiers.")

with tab_method:
    st.markdown("""**Superficie :** calcul géodésique sur ellipsoïde WGS84; inclut les
surfaces représentées par les polygones, qui peuvent comprendre de l'eau.

**Statistiques :** le CSV doit déjà être validé et harmonisé à l'échelle des quartiers.
Les aires de diffusion du recensement ne correspondent pas exactement aux quartiers;
l'interpolation spatiale doit être documentée. Les revenus médians ne s'additionnent pas.

**Modèles prédictifs :** non développés à ce stade. Aucune prédiction n'est simulée.""")
    st.markdown("[Données ouvertes de Québec](https://www.ville.quebec.qc.ca/services/donnees-services-ouverts/) · [Statistique Canada](https://www.statcan.gc.ca/fr/geographie)")

st.caption("Données spatiales : Ville de Québec, Données Québec · GeoInsight AI 2.0")
