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
from branca.colormap import LinearColormap

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.regions import REGIONS
from app.decoupages import charger_subdivisions
from app.geo_shapes import construire_regions
from app.name_matching import normaliser_nom, rapprochement
from app.quartier_bi import preparer_couche
GEOJSON = ROOT / "data" / "quartiers.geojson"
CSV = ROOT / "data" / "indicateurs_quartiers.csv"
CSV_REFERENCE = ROOT / "data" / "indicateurs_quartiers_2021.csv"
GEOD = Geod(ellps="WGS84")

st.set_page_config(page_title="GeoInsight AI | Intelligence territoriale", page_icon="🌎", layout="wide")
st.markdown("<style>" + (ROOT / "app" / "design.css").read_text(encoding="utf-8") + "</style>", unsafe_allow_html=True)

def normaliser(value):
    return normaliser_nom(value)

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
        "geometryPrecision": 6
    }, timeout=90)
    response.raise_for_status()
    payload = response.json()
    if payload.get("type") != "FeatureCollection" or not payload.get("features"):
        raise ValueError("Le service officiel n'a pas renvoyé de régions GeoJSON.")
    # Validation des anneaux et réparation topologique sans fabriquer de rectangles.
    noms_officiels = {code: nom for code, nom, _lat, _lon in REGIONS}
    regions = construire_regions(payload["features"], noms_officiels)
    if len(regions) != 17:
        raise ValueError(f"Nombre de régions inattendu : {len(regions)} (17 attendues).")
    return regions

st.sidebar.markdown("## 🌎 GeoInsight AI")
st.sidebar.caption("EXPLORATION TERRITORIALE")
st.sidebar.markdown("### 🧭 Navigation géographique")
st.markdown("""<div class="geo-hero"><div class="geo-eyebrow">GEOINSIGHT AI · QUÉBEC</div>
<h1>Comprendre les territoires.<br>Éclairer les décisions.</h1>
<p>Analyse géospatiale · Cartographie interactive · Intelligence territoriale</p></div>""", unsafe_allow_html=True)

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
    st.markdown('<div class="geo-section-label">Tableau de bord territorial</div>', unsafe_allow_html=True)
    kpi1, kpi2, kpi3, kpi4 = st.columns([1, 1.25, 1, 1.2])
    kpi1.metric("Régions administratives", len(regions))
    kpi2.metric("Niveau d’exploration", niveau)
    kpi3.metric("Territoires affichés", len(visibles))
    kpi4.metric("Données socioéconomiques", "À intégrer")
    st.markdown('<div class="geo-section-label">Carte et détails du territoire</div>', unsafe_allow_html=True)

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
    carte_col, details_col = st.columns([3.4, 1.25], gap="medium")
    with carte_col:
        # La clé change au choix d'un territoire : Leaflet recadre alors la carte.
        selection_key = "|".join([
            selection_region,
            locals().get("selection_mrc", ""),
            locals().get("selection_mun", ""),
        ])
        st_folium(carte, height=690, use_container_width=True,
                  returned_objects=[], key=f"province-map:{selection_key}")
    with details_col:
        st.markdown("#### 📍 Territoire sélectionné")
        if len(visibles) == 1:
            props = visibles[0]["properties"]
            st.markdown(f"### {props['nom']}")
            st.caption(f"Code administratif : {props['code']}")
        else:
            st.markdown(f"### {niveau}")
            st.caption(f"{len(visibles)} territoires affichés")
        st.divider()
        st.markdown("**Niveau actuel**")
        st.write(niveau)
        st.markdown("**Données géographiques**")
        st.success("Limites cartographiques disponibles")
        st.markdown("**Indicateurs économiques et démographiques**")
        st.info("En préparation — aucune valeur simulée.")
        st.markdown("**Explorer davantage**")
        st.caption("Utilisez les sélections successives de la barre latérale.")
    st.caption("Source : MRNF — Découpages administratifs du Québec. Géométries réparées et simplifiées pour affichage.")
    st.caption("Les quartiers sont disponibles pour la ville de Québec lorsqu’elle est sélectionnée; ailleurs, leur couverture dépend des données existantes.")
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

source = uploaded if uploaded is not None else (CSV if CSV.exists() else CSV_REFERENCE if CSV_REFERENCE.exists() else None)
socio = None
if source is not None:
    try:
        socio = charger_indicateurs(source)
    except (UnicodeError, ValueError, pd.errors.ParserError) as error:
        st.error(f"Le CSV n'a pas été intégré : {error}")

merged = territoires.copy()
if socio is not None:
    try:
        matches, unmatched = rapprochement(
            socio["quartier"].tolist(), territoires["quartier"].tolist()
        )
    except ValueError as error:
        st.error(f"Correspondances géographiques ambiguës : {error}")
        st.stop()

    # Utiliser les libellés géographiques validés; préserver intactes les populations.
    socio = socio.copy()
    socio["key"] = socio["quartier"].map(
        lambda nom: normaliser(matches.get(nom, nom))
    )
    if socio["key"].duplicated().any():
        st.error("Des noms du CSV correspondent au même quartier : vérifiez le fichier.")
        st.stop()

    coverage = len(matches)
    if unmatched:
        st.warning(
            f"{coverage}/{len(socio)} quartiers du CSV ont été associés. "
            f"Restent sans correspondance : {', '.join(unmatched)}"
        )
    else:
        st.success(f"CSV associé aux {coverage} quartiers. Population et autres indicateurs conservés.")

    merged = merged.merge(
        socio.drop(columns=["quartier"]), on="key", how="left", validate="one_to_one"
    )
    if "population" in merged:
        merged["densite_hab_km2"] = (
            merged["population"] / merged["superficie_km2"].replace(0, float("nan"))
        )
filtered = merged if selected == "Tous les quartiers" else merged[merged["quartier"] == selected]

tab_map, tab_analysis, tab_method = st.tabs(["🗺️ Carte", "📊 Analyses", "📚 Méthode"])
with tab_map:
    c1, c2, c3 = st.columns(3)
    c1.metric("Quartiers affichés", len(filtered))
    c2.metric("Superficie des polygones", f"{filtered['superficie_km2'].sum():.1f} km²")
    if "population" in filtered and filtered["population"].notna().all():
        c3.metric("Population (2021)", f"{filtered['population'].sum():,.0f}".replace(",", " "))
    else:
        c3.metric("Population (2021)", "Partielle ou indisponible")

    modes = {
        "Population (2021)": "population",
        "Densité (hab./km²)": "densite_hab_km2",
        "Limites des quartiers": None,
    }
    mode = st.radio("Couche thématique", list(modes), horizontal=True,
                    help="Population et densité calculées uniquement à partir de données disponibles.")
    metric = modes[mode]
    selected_names = set(filtered["quartier"])
    visible = [z for z in zones if z["quartier"] in selected_names]
    couche, valeurs = preparer_couche(
        visible, filtered.to_dict("records"), normaliser, metric or "population"
    )
    m = folium.Map(location=[46.8139, -71.2080], zoom_start=11,
                   tiles="OpenStreetMap", control_scale=True)

    color_scale = None
    if metric and valeurs:
        vmin, vmax = min(valeurs), max(valeurs)
        if vmin == vmax:
            vmax = vmin + 1
        color_scale = LinearColormap(
            ["#edf8f7", "#9fdbdc", "#46aab5", "#155b78"],
            vmin=vmin, vmax=vmax,
            caption="Population (habitants)" if metric == "population"
                    else "Densité (habitants par km²)",
        )
        color_scale.add_to(m)
    elif metric:
        st.info("Aucune donnée numérique disponible pour cette couche.")

    if show_borders:
        def colorier(feature):
            value = feature["properties"]["valeur"]
            return {
                "color": "#146478", "weight": 1.7,
                "fillColor": color_scale(value) if color_scale and value is not None else "#bed5da",
                "fillOpacity": 0.70 if color_scale and value is not None else 0.22,
            }

        folium.GeoJson(
            couche,
            name="Quartiers de Québec",
            tooltip=folium.GeoJsonTooltip(
                fields=["NOM", "Population", "Superficie", "Densité"],
                aliases=["Quartier :", "Population 2021 :", "Superficie :", "Densité :"],
                sticky=True,
            ),
            popup=folium.GeoJsonPopup(
                fields=["NOM", "Population", "Superficie", "Densité"],
                aliases=["Quartier :", "Population :", "Superficie :", "Densité :"],
                labels=True,
            ),
            style_function=colorier,
            highlight_function=lambda _: {"color": "#ff9d2e", "weight": 3.5,
                                          "fillOpacity": 0.84},
        ).add_to(m)

    if visible:
        bounds = [shape(z["geometry"]).bounds for z in visible]
        bounds = [b for b in bounds if all(float("-inf") < x < float("inf") for x in b)]
        if bounds:
            m.fit_bounds(
                [[min(b[1] for b in bounds), min(b[0] for b in bounds)],
                 [max(b[3] for b in bounds), max(b[2] for b in bounds)]],
                padding_top_left=(16, 16),
                padding_bottom_right=(16, 16),
                max_zoom=15,
            )
    folium.LayerControl().add_to(m)
    st_folium(
        m, height=670, use_container_width=True, returned_objects=[],
        key=f"quartiers-map:{selected}:{show_borders}:{mode}",
    )
    st.caption("Clique sur un quartier pour consulter sa fiche; les couleurs sont relatives "
               "aux quartiers actuellement affichés et ne constituent pas des prévisions.")

with tab_analysis:
    st.subheader("Indicateurs territoriaux")
    if socio is None:
        st.info("Les superficies sont disponibles. Importez des données fiables pour la population.")
    fields = ["quartier", "superficie_km2"] + [
        k for k in ("population", "densite_hab_km2", "revenu_median", "annee", "source")
        if k in filtered.columns
    ]
    st.dataframe(filtered[fields].sort_values("quartier"),
                 use_container_width=True, hide_index=True)
    st.download_button(
        "Exporter les indicateurs (CSV)",
        data=filtered[fields].to_csv(index=False).encode("utf-8-sig"),
        file_name="geoinsight_quebec_indicateurs.csv", mime="text/csv",
    )

    chart_options = ["superficie_km2"] + [
        k for k in ("population", "densite_hab_km2", "revenu_median")
        if k in filtered and filtered[k].notna().any()
    ]
    indicateur = st.selectbox("Comparer visuellement les quartiers", chart_options)
    graphique = (filtered[["quartier", indicateur]]
                 .dropna().set_index("quartier")
                 .sort_values(indicateur, ascending=False))
    if not graphique.empty:
        st.bar_chart(graphique, horizontal=True)

    st.divider()
    st.subheader("Comparer deux quartiers")
    liste_comparaison = sorted(merged["quartier"].tolist())
    colonne_a, colonne_b = st.columns(2)
    with colonne_a:
        quartier_a = st.selectbox("Quartier A", liste_comparaison, index=0)
    with colonne_b:
        quartier_b = st.selectbox("Quartier B", liste_comparaison,
                                 index=1 if len(liste_comparaison) > 1 else 0)
    if quartier_a == quartier_b:
        st.info("Choisissez deux quartiers différents pour les comparer.")
    else:
        couple = merged.set_index("quartier").loc[[quartier_a, quartier_b]]
        comparaison = couple[[k for k in (
            "superficie_km2", "population", "densite_hab_km2", "revenu_median"
        ) if k in couple.columns]].T
        comparaison.index = [
            {"superficie_km2": "Superficie (km²)",
             "population": "Population (2021)",
             "densite_hab_km2": "Densité (hab./km²)",
             "revenu_median": "Revenu médian (si renseigné)"}.get(k, k)
            for k in comparaison.index
        ]
        st.dataframe(comparaison, use_container_width=True)

    if socio is not None and "population" in merged:
        st.caption(f"Population : {merged['population'].notna().sum()}/{len(merged)} "
                   "quartiers renseignés. Les effectifs peuvent différer légèrement "
                   "du total municipal en raison des arrondis du recensement.")

with tab_method:
    st.markdown("""**Superficie :** calcul géodésique sur ellipsoïde WGS84; inclut les
surfaces représentées par les polygones, qui peuvent comprendre de l'eau.

**Statistiques :** le CSV doit déjà être validé et harmonisé à l'échelle des quartiers.
Les aires de diffusion du recensement ne correspondent pas exactement aux quartiers;
l'interpolation spatiale doit être documentée. Les revenus médians ne s'additionnent pas.

**Modèles prédictifs :** non développés à ce stade. Aucune prédiction n'est simulée.""")
    st.markdown("[Données ouvertes de Québec](https://www.ville.quebec.qc.ca/services/donnees-services-ouverts/) · [Statistique Canada](https://www.statcan.gc.ca/fr/geographie)")

st.caption("Données spatiales : Ville de Québec, Données Québec · GeoInsight AI 2.0")
