"""GeoInsight AI — plateforme géospatiale extensible, pilote initial à Québec."""
from pathlib import Path
import json
import unicodedata

import folium
import pandas as pd
import streamlit as st
from pyproj import Geod
from shapely.geometry import shape
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parents[1]
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

st.title("🌎 GeoInsight AI")
st.caption("Plateforme de Business Intelligence géospatiale — extensible à plusieurs territoires")
st.caption("Territoire actuellement disponible : ville de Québec (pilote)")
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
    st.selectbox("Territoire", ["Québec, Canada — pilote"], help="D’autres villes seront ajoutées dans les prochaines versions.")
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
