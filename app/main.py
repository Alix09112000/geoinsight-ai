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
from app.regions import REGIONS
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
GEOJSON = ROOT / "data" / "quartiers.geojson"
CSV = ROOT / "data" / "indicateurs_quartiers.csv"
GEOD = Geod(ellps="WGS84")

st.set_page_config(page_title="GeoInsight AI | Intelligence territoriale", page_icon="🌎", layout="wide")
st.markdown("<style>" + (ROOT / "app" / "design.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)

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
    # Le service peut renvoyer plusieurs morceaux de polygone pour une même région.
    # Agrégation par code officiel, sans perte de géométries.
    noms_officiels = {code: nom for code, nom, _lat, _lon in REGIONS}
    grouped = {}
    for feature in payload["features"]:
        props = feature.get("properties") or {}
        raw_code = str(props.get("RES_CO_REG") or "").strip()
        name = str(props.get("RES_NM_REG") or "").strip()
        geometry = feature.get("geometry")
        if not raw_code.isdigit() or not geometry:
            continue
        code = raw_code.zfill(2)
        if geometry.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        if code not in noms_officiels:
            continue
        group = grouped.setdefault(code, {"nom": noms_officiels[code], "parts": []})
        # MultiPolygon brut : pas d'union topologique sur des sources parfois invalides.
        coordinates = geometry.get("coordinates") or []
        if geometry["type"] == "Polygon":
            if coordinates:
                group["parts"].append(coordinates)
        else:
            group["parts"].extend(part for part in coordinates if part)

    regions = []
    for code, group in sorted(grouped.items()):
        if not group["parts"]:
            continue
        regions.append({"type": "Feature",
                        "properties": {"code": code, "nom": group["nom"]},
                        "geometry": {"type": "MultiPolygon", "coordinates": group["parts"]}})
    if len(regions) != 17:
        raise ValueError(f"Nombre de régions inattendu : {len(regions)} (17 attendues).")
    return regions

from app.decoupages import charger_subdivisions

st.sidebar.title("◈ GeoInsight AI")
st.sidebar.caption("INTELLIGENCE TERRITORIALE  /  QUÉBEC")
st.markdown("""<div class="geo-hero"><div class="geo-eyebrow">GEOINSIGHT AI · EXPLORATEUR</div>
<h1>Comprendre les territoires. Éclairer les décisions.</h1>
<p>Explorez les régions, les MRC et les municipalités du Québec sur une carte interactive.</p>
</div>""", unsafe_allow_html=True)

# Navigation en cascade, sans changer de vue.
try:
    regions = sorted(charger_regions(), key=lambda f: f["properties"]["code"])
except (requests.RequestException, ValueError, TypeError) as error:
    st.error("Les limites des régions ne sont pas disponibles actuellement.")
    st.caption(str(error))
    st.stop()

regional_options = {"Toute la province": None}
regional_options.update({
    f'{r["properties"]["code"]} — {r["properties"]["nom"]}': r
    for r in regions
})
with st.sidebar:
    selection_region = st.selectbox("1. Région administrative", list(regional_options))
region = regional_options[selection_region]
visibles = regions if region is None else [region]
niveau = "Régions administratives"
quartiers_actifs = False

if region is not None:
    code_region = region["properties"]["code"]
    try:
        mrcs = charger_subdivisions("mrc", code_region)
    except (requests.RequestException, ValueError, TypeError) as error:
        st.warning(f"MRC indisponibles pour cette région : {error}")
        mrcs = []
    if mrcs:
        mrc_options = {"Toutes les MRC": None}
        mrc_options.update({
            f'{m["properties"]["code"]} — {m["properties"]["nom"]}': m
            for m in mrcs
        })
        with st.sidebar:
            selection_mrc = st.selectbox("2. MRC ou territoire équivalent", list(mrc_options))
        mrc = mrc_options[selection_mrc]
        visibles = mrcs if mrc is None else [mrc]
        niveau = "MRC et territoires équivalents"
        if mrc is not None:
            try:
                municipalites = charger_subdivisions("municipalite", mrc["properties"]["code"])
            except (requests.RequestException, ValueError, TypeError) as error:
                st.warning(f"Municipalités indisponibles : {error}")
                municipalites = []
            if municipalites:
                mun_options = {"Toutes les municipalités": None}
                mun_options.update({
                    f'{m["properties"]["code"]} — {m["properties"]["nom"]}': m
                    for m in municipalites
                })
                with st.sidebar:
                    selection_mun = st.selectbox("3. Municipalité", list(mun_options))
                mun = mun_options[selection_mun]
                visibles = municipalites if mun is None else [mun]
                niveau = "Municipalités"
                if mun is not None and normaliser(mun["properties"]["nom"]) == "quebec":
                    quartiers_actifs = st.sidebar.checkbox(
                        "4. Explorer les quartiers de Québec", value=False
                    )

if not quartiers_actifs:
    st.markdown('<div class="geo-section-label">Vue cartographique · Exploration territoriale</div>', unsafe_allow_html=True)
    st.caption("Affinez votre exploration avec les filtres géographiques dans le menu latéral.")
    left, right = st.columns(2)
    left.metric("Échelle géographique", niveau)
    right.metric("Entités visibles", len(visibles))

    carte = folium.Map(location=[49.6, -71.4], zoom_start=5,
                       tiles="OpenStreetMap", control_scale=True)
    if visibles:
        folium.GeoJson(
            {"type": "FeatureCollection", "features": visibles},
            name=niveau,
            tooltip=folium.GeoJsonTooltip(fields=["code", "nom"],
                                          aliases=["Code :", "Nom :"]),
            style_function=lambda _: {"color": "#087f8c", "weight": 1.8,
                                      "fillColor": "#21a0a6", "fillOpacity": 0.16},
            highlight_function=lambda _: {"color": "#ff9d2e", "weight": 3,
                                          "fillOpacity": 0.35},
        ).add_to(carte)
        # Calcul de cadrage à partir des coordonnées, sans union topologique GEOS.
        extent = [shape(f["geometry"]).bounds for f in visibles]
        if region is None:
            # Vue provinciale plus lisible : cadrage conservant le Québec méridional.
            carte.location = [49.6, -71.4]
            carte.options["zoom"] = 5
        else:
            carte.fit_bounds([[min(x[1] for x in extent), min(x[0] for x in extent)],
                              [max(x[3] for x in extent), max(x[2] for x in extent)]])
    folium.LayerControl().add_to(carte)
    st_folium(carte, height=650, use_container_width=True, returned_objects=[])
    st.caption("Source des limites : MRNF, service de découpages administratifs du Québec.")
    st.info("Le détail des quartiers est actuellement disponible pour la ville de Québec. "
            "Les autres villes seront ajoutées lorsque des découpages fiables seront disponibles.")
    st.stop()

st.caption("Navigation : Province → Capitale-Nationale → territoire équivalent → Québec → quartiers")
st.subheader("Analyse locale · Quartiers de Québec")
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
    selected = st.selectbox("5. Quartier de Québec", ["Tous les quartiers"] + names)
    show_borders = st.checkbox("Afficher les limites des quartiers", value=True)
    uploaded = st.file_uploader("Importer des indicateurs CSV vérifiés", type="csv")

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
