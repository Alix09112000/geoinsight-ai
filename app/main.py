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
from app.ui import header, inspector, map_object, section, legend_choropleth
from app.quebec_mask import masque_hors_quebec, ajouter_masque
from app.regional_bi import tableau_regions, comparer_regions
from app.socioeconomic import INDICATEURS, charger_indicateurs_regions, joindre_indicateurs_regions, format_indicateur
GEOJSON = ROOT / "data" / "quartiers.geojson"
CSV = ROOT / "data" / "indicateurs_quartiers.csv"
CSV_REFERENCE = ROOT / "data" / "indicateurs_quartiers_2021.csv"
CSV_REGIONS_ISQ = ROOT / "data" / "indicateurs_regions_isq.csv"
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

@st.cache_data(ttl=86400, show_spinner=False)
def charger_masque_provincial(les_regions):
    return masque_hors_quebec(les_regions)


@st.cache_data(ttl=86400, show_spinner=False)
def calculer_superficies_regionales(regions_officielles):
    return tableau_regions(regions_officielles)


st.sidebar.markdown("## 🌐 GeoInsight AI")
st.sidebar.caption("EXPLORER LE QUÉBEC")
st.sidebar.markdown("### 🗺️ Exploration territoriale")
header()

# Navigation en cascade, sans changer de vue.
try:
    regions = sorted(charger_regions(), key=lambda f: f["properties"]["code"])
except (requests.RequestException, ValueError, TypeError) as error:
    st.error("Les limites des régions ne sont pas disponibles actuellement.")
    st.caption(str(error))
    st.stop()

try:
    masque_province, limites_province = charger_masque_provincial(regions)
except Exception as erreur_masque:
    # La carte ne doit jamais révéler les territoires voisins en cas d'erreur.
    masque_province, limites_province = None, None
    st.warning("Les limites provinciales ne peuvent pas être masquées actuellement : "
               "affichage sans fond de carte en attendant leur réparation.")
    st.caption(f"Détail technique du masque : {erreur_masque}")

try:
    indicateurs_regionaux = charger_indicateurs_regions(CSV_REGIONS_ISQ)
    indicateurs_isq = joindre_indicateurs_regions(regions, indicateurs_regionaux)
except (OSError, ValueError, TypeError) as error_isq:
    indicateurs_regionaux, indicateurs_isq = [], {}
    st.warning("Les indicateurs régionaux ISQ ne sont pas disponibles : "
               "les cartes administratives restent accessibles.")
    st.caption(str(error_isq))

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

fond_carte = st.sidebar.radio(
    "Fond de carte", ["Plan", "Satellite"], horizontal=True, key="geo_fond_carte"
)

if not quartiers_actifs:
    section("Vue d'ensemble", "Exploration administrative du Québec")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4, gap="small")
    ligne_region = indicateurs_isq.get(region["properties"]["code"]) if region is not None else None
    kpi1.metric("Régions du Québec", len(regions))
    kpi2.metric("Échelle actuelle",
                {"Régions administratives": "Régions",
                 "MRC et territoires équivalents": "MRC / TE",
                 "Municipalités": "Municipalités"}.get(niveau, niveau))
    kpi3.metric("Territoires affichés", len(visibles))
    if indicateurs_isq:
        population_kpi = (ligne_region["population_2025"] if ligne_region
                          else sum(row["population_2025"] for row in indicateurs_isq.values()))
        kpi4.metric("Population régionale 2025" if ligne_region else "Population Québec 2025",
                    f"{population_kpi:,}".replace(",", " "))
    else:
        kpi4.metric("Population (2025)", "Indisponible")
    section("Carte des territoires", "Plan et satellite · limites officielles")
    theme_regional = "Limites administratives"
    if region is None and indicateurs_isq:
        theme_regional = st.selectbox(
            "Carte thématique — 17 régions",
            ["Limites administratives"] + list(INDICATEURS),
            format_func=lambda value: INDICATEURS[value][0]
            if value in INDICATEURS else value,
            key="carte_thematique_regions",
        )

    carte = (map_object(location=[52.5, -71.5], zoom=5, fond=fond_carte)
             if masque_province is not None else
             folium.Map(location=[52.5, -71.5], zoom_start=5, tiles=None,
                        control_scale=True))
    carte.options["maxBounds"] = [[41.5, -87.0], [65.0, -51.0]]
    carte.options["maxBoundsViscosity"] = 1.0
    colormap_regions = None
    if visibles:
        if theme_regional in INDICATEURS and indicateurs_isq:
            values = [line[theme_regional] for line in indicateurs_isq.values()]
            colormap_regions = LinearColormap(
                ["#e9f6f7", "#95d2d7", "#3299b2", "#0b4b6d"],
                vmin=min(values), vmax=max(values),
                caption=INDICATEURS[theme_regional][0],
            )
            _, _, annee_theme = INDICATEURS[theme_regional]
            couche_visible = [{
                "type": "Feature", "geometry": f["geometry"],
                "properties": {
                    **f["properties"],
                    "indicateur": format_indicateur(
                        indicateurs_isq[f["properties"]["code"]][theme_regional],
                        theme_regional,
                    ),
                    "annee": str(annee_theme),
                },
            } for f in visibles]
            def style_region(feature):
                val = indicateurs_isq[feature["properties"]["code"]][theme_regional]
                return {
                    "color": "#065b7a", "weight": 1.4,
                    "fillColor": colormap_regions(val), "fillOpacity": .73,
                }
            tooltip = folium.GeoJsonTooltip(
                fields=["code", "nom", "indicateur", "annee"],
                aliases=["Code :", "Région :", "Indicateur :", "Année :"],
            )
        else:
            couche_visible = visibles
            def style_region(_):
                return {"color": "#087f8c", "weight": 1.8,
                        "fillColor": "#21a0a6", "fillOpacity": 0.16}
            tooltip = folium.GeoJsonTooltip(
                fields=["code", "nom"], aliases=["Code :", "Nom :"]
            )

        folium.GeoJson(
            {"type": "FeatureCollection", "features": couche_visible},
            name=niveau, tooltip=tooltip, style_function=style_region,
            highlight_function=lambda _: {
                "color": "#ff9d2e", "weight": 3, "fillOpacity": 0.55
            },
        ).add_to(carte)
        # Calcul de cadrage à partir des coordonnées, sans union topologique GEOS.
        extent = [shape(f["geometry"]).bounds for f in visibles]
        if region is None:
            # Cadrage sur l'ensemble du Québec (et jamais sur l'enveloppe du masque).
            bounds = limites_province or (
                min(x[0] for x in extent), min(x[1] for x in extent),
                max(x[2] for x in extent), max(x[3] for x in extent)
            )
            carte.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
                             padding_top_left=(18, 18),
                             padding_bottom_right=(18, 18))
        else:
            carte.fit_bounds([[min(x[1] for x in extent), min(x[0] for x in extent)],
                              [max(x[3] for x in extent), max(x[2] for x in extent)]])
    if masque_province is not None:
        ajouter_masque(carte, masque_province)
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
                  returned_objects=[],
                  key=f"province-map:{selection_key}:{fond_carte}:{theme_regional}")
        if colormap_regions is not None:
            legend_choropleth(
                INDICATEURS[theme_regional][0],
                colormap_regions.vmin, colormap_regions.vmax,
            )
    with details_col:
        props = visibles[0]["properties"] if len(visibles) == 1 else None
        inspector(
            nom=props["nom"] if props else "Province de Québec",
            niveau=niveau,
            code=props["code"] if props else None,
            population=(
                f"{ligne_region['population_2025']:,}".replace(",", " ")
                if ligne_region else None
            ),
            population_annee=2025,
            note=(
                "La population indiquée concerne la région administrative choisie "
                "(2025), même si la carte affiche une MRC ou une municipalité. "
                "Source : Institut de la statistique du Québec."
                if ligne_region else
                "Les quatre indicateurs socioéconomiques régionaux sont disponibles "
                "dans le panneau d'analyse sous la carte. "
                "Source : Institut de la statistique du Québec."
            ),
        )
    st.caption("Source : MRNF — Découpages administratifs du Québec. Géométries réparées et simplifiées pour affichage.")
    st.caption("Les quartiers sont disponibles pour la ville de Québec lorsqu’elle est sélectionnée; ailleurs, leur couverture dépend des données existantes.")

    if indicateurs_regionaux:
        with st.expander("📈 Données socioéconomiques officielles — 17 régions", expanded=True):
            st.caption(
                "Source : Institut de la statistique du Québec (ISQ). "
                "Population et 65+ : 2025 ; faible revenu des familles : 2023 ; "
                "revenu disponible par habitant : 2024 (provisoire). "
                "Ces indicateurs ont des unités et des années différentes."
            )
            col_metric, col_coverage = st.columns([3, 1])
            with col_metric:
                champ_socio = st.selectbox(
                    "Indicateur à comparer",
                    list(INDICATEURS),
                    format_func=lambda item: INDICATEURS[item][0],
                    key="indicator_regions_chart",
                )
            with col_coverage:
                st.metric("Régions couvertes", f"{len(indicateurs_regionaux)}/17")
            titre_indicateur, _, annee_indicateur = INDICATEURS[champ_socio]
            frame_isq = pd.DataFrame(indicateurs_regionaux)
            ordre_isq = frame_isq.sort_values(champ_socio, ascending=False)
            st.bar_chart(
                ordre_isq.set_index("nom_region")[[champ_socio]],
                horizontal=True,
            )
            st.caption(
                f"Classement par : {titre_indicateur}. "
                "La comparaison porte uniquement sur des régions administratives, "
                "sans extrapolation aux MRC."
            )
            region_a, region_b = st.columns(2)
            options_isq = sorted(
                [(row["code_region"], row["nom_region"]) for row in indicateurs_regionaux]
            )
            def format_region(code):
                return f"{code} — {indicateurs_isq[code]['nom_region']}"
            with region_a:
                first_code = st.selectbox(
                    "Comparer : région A",
                    [item[0] for item in options_isq],
                    format_func=format_region, key="regional_isq_a",
                )
            with region_b:
                second_code = st.selectbox(
                    "Comparer : région B",
                    [item[0] for item in options_isq],
                    index=1, format_func=format_region, key="regional_isq_b",
                )
            if first_code != second_code:
                first_isq, second_isq = indicateurs_isq[first_code], indicateurs_isq[second_code]
                lines_isq = [{
                    "Indicateur": info[0],
                    "Année": info[2],
                    first_isq["nom_region"]: format_indicateur(first_isq[field], field),
                    second_isq["nom_region"]: format_indicateur(second_isq[field], field),
                } for field, info in INDICATEURS.items()]
                st.dataframe(pd.DataFrame(lines_isq), hide_index=True,
                             use_container_width=True)
            else:
                st.info("Choisissez deux régions différentes pour la comparaison.")
            with st.popover("Afficher les données et les sources"):
                for _, record in frame_isq.sort_values("code_region").iterrows():
                    st.markdown(f"[{record['code_region']} — {record['nom_region']}]({record['source']})")
            st.download_button(
                "⬇️ Télécharger les indicateurs officiels (CSV)",
                data=frame_isq.to_csv(index=False).encode("utf-8-sig"),
                file_name="geoinsight_indicateurs_isq_regions.csv",
                mime="text/csv", key="export_region_isq",
            )
            st.caption(
                "Attention : le découpage administratif a changé en Estrie et "
                "en Chaudière-Appalaches. Consultez les notes méthodologiques "
                "de chaque fiche régionale avant une analyse causale."
            )

    # BI provinciale descriptive : aucun chiffre démographique extrapolé.
    with st.expander("📊 Analyse comparative des 17 régions", expanded=False):
        st.caption(
            "Superficies géodésiques **estimées** à partir des limites cartographiques "
            "simplifiées du MRNF (WGS84). Les valeurs ne constituent pas des "
            "superficies légales officielles et peuvent inclure des plans d'eau."
        )
        try:
            rows_regions = calculer_superficies_regionales(regions)
        except (ValueError, TypeError, OverflowError) as analyse_error:
            st.warning("Impossible de calculer les superficies régionales.")
            st.caption(str(analyse_error))
        else:
            geo_table = pd.DataFrame(rows_regions)
            metric_col = "Superficie géodésique estimée (km²)"
            geo_sorted = geo_table.sort_values(metric_col, ascending=False)
            c_top, c_count = st.columns(2)
            c_top.metric("Plus grande superficie estimée",
                         geo_sorted.iloc[0]["Région administrative"])
            c_count.metric("Régions analysées", len(geo_sorted))
            st.bar_chart(
                geo_sorted.set_index("Région administrative")[[metric_col]],
                horizontal=True,
            )
            st.dataframe(
                geo_table, use_container_width=True, hide_index=True
            )
            st.download_button(
                "⬇️ Exporter les superficies des régions (CSV)",
                data=geo_table.to_csv(index=False).encode("utf-8-sig"),
                file_name="geoinsight_regions_superficies_estimees.csv",
                mime="text/csv",
                key="export_regions_superficies",
            )
            st.markdown("##### Comparer deux régions")
            codes_region = geo_table["Code régional"].tolist()
            names_region = dict(zip(
                geo_table["Code régional"],
                geo_table["Région administrative"],
            ))
            first, second = st.columns(2)
            with first:
                code_a = st.selectbox(
                    "Région A", codes_region,
                    format_func=lambda code: names_region[code],
                    key="regional_compare_a",
                )
            with second:
                code_b = st.selectbox(
                    "Région B", codes_region,
                    index=1 if len(codes_region) > 1 else 0,
                    format_func=lambda code: names_region[code],
                    key="regional_compare_b",
                )
            if code_a != code_b:
                st.dataframe(
                    pd.DataFrame([comparer_regions(rows_regions, code_a, code_b)]),
                    hide_index=True, use_container_width=True,
                )
            else:
                st.info("Choisis deux régions différentes.")
    st.stop()

section("Quartiers de la ville de Québec", "Données municipales et population du recensement 2021")
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
        st.caption(f"✓ Indicateurs associés à {coverage} quartiers — source et millésime conservés.")

    merged = merged.merge(
        socio.drop(columns=["quartier"]), on="key", how="left", validate="one_to_one"
    )
    if "population" in merged:
        merged["densite_hab_km2"] = (
            merged["population"] / merged["superficie_km2"].replace(0, float("nan"))
        )
filtered = merged if selected == "Tous les quartiers" else merged[merged["quartier"] == selected]

population_complete = (
    "population" in filtered.columns
    and not filtered.empty
    and filtered["population"].notna().all()
)
total_population = (
    int(filtered["population"].sum()) if population_complete else None
)
area_total = float(filtered["superficie_km2"].sum())
section("Tableau de bord démographique", "Quartiers de Québec · Recensement 2021")
k1, k2, k3, k4 = st.columns(4, gap="small")
k1.metric("Quartiers affichés", len(filtered))
k2.metric("Population (2021)",
          f"{total_population:,}".replace(",", " ") if total_population is not None else "Indisponible")
k3.metric("Superficie", f"{area_total:,.1f} km²".replace(",", " "))
k4.metric("Densité (hab./km²)",
          f"{(total_population / area_total):,.0f}".replace(",", " ")
          if total_population is not None and area_total > 0 else "Indisponible")

tab_map, tab_analysis, tab_method = st.tabs(["🗺️ Explorer la carte", "📊 Analyse et comparaison", "📚 Sources et méthode"])
with tab_map:
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
    m = (map_object(location=[46.8139, -71.2080], zoom=11, fond=fond_carte)
         if masque_province is not None else
         folium.Map(location=[46.8139, -71.2080], zoom_start=11, tiles=None,
                    control_scale=True))
    m.options["maxBounds"] = [[41.5, -87.0], [65.0, -51.0]]
    m.options["maxBoundsViscosity"] = 1.0

    color_scale = None
    legende_active = False
    if metric and valeurs:
        vmin, vmax = min(valeurs), max(valeurs)
        # Une seule zone n'offre aucune variation statistique à cartographier.
        legende_active = len(visible) > 1 and vmin < vmax
        if legende_active:
            color_scale = LinearColormap(
                ["#edf8f7", "#9fdbdc", "#46aab5", "#155b78"],
                vmin=vmin, vmax=vmax,
                caption="Population (habitants)" if metric == "population"
                        else "Densité (habitants par km²)",
                max_labels=3,
            )
    elif metric:
        st.info("Aucune donnée numérique disponible pour cette couche.")

    if show_borders:
        def colorier(feature):
            value = feature["properties"]["valeur"]
            colored = color_scale is not None and value is not None
            return {
                "color": "#087f8c", "weight": 2.2 if len(visible) == 1 else 1.7,
                "fillColor": color_scale(value) if colored else "#56b4c2",
                # Imagerie satellite lisible ; pas d'aplat opaque sur un seul quartier.
                "fillOpacity": (0.30 if fond_carte == "Satellite" else 0.62)
                               if colored else (0.12 if fond_carte == "Satellite" else 0.20),
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
    if masque_province is not None:
        ajouter_masque(m, masque_province)
    folium.LayerControl().add_to(m)
    section("Visualisation géospatiale", "Clique sur un polygone pour ses informations")
    col_map, col_fiche = st.columns([3.35, 1.2], gap="small")
    with col_map:
        st_folium(
            m, height=615, use_container_width=True, returned_objects=[],
            key=f"quartiers-map:{selected}:{show_borders}:{mode}:{fond_carte}",
        )
        if legende_active:
            legend_choropleth(
                "Population (habitants, 2021)" if metric == "population"
                else "Densité (habitants / km²)", vmin, vmax
            )
        elif metric and len(visible) == 1:
            st.caption("Quartier sélectionné : ses valeurs figurent dans la fiche à droite.")
    with col_fiche:
        row = filtered.iloc[0] if selected != "Tous les quartiers" and len(filtered) else None
        local_population = (
            f"{int(row['population']):,}".replace(",", " ")
            if row is not None and "population" in filtered.columns
            and pd.notna(row.get("population")) else None
        )
        local_area = (
            f"{row['superficie_km2']:.2f} km²" if row is not None else f"{area_total:.1f} km²"
        )
        local_density = (
            f"{row['densite_hab_km2']:,.0f} hab./km²".replace(",", " ")
            if row is not None and "densite_hab_km2" in filtered.columns
            and pd.notna(row.get("densite_hab_km2")) else None
        )
        inspector(
            nom=selected if row is not None else "Ville de Québec · Quartiers",
            niveau="Quartier" if row is not None else "35 quartiers disponibles",
            population=local_population if row is not None else (
                f"{total_population:,}".replace(",", " ")
                if total_population is not None else None),
            superficie=local_area,
            densite=local_density if row is not None else (
                f"{total_population / area_total:,.0f} hab./km²".replace(",", " ")
                if total_population is not None and area_total else None),
            note="Population : recensement 2021. Densité calculée à partir des polygones municipaux ; les surfaces peuvent inclure des plans d'eau.",
        )
    st.caption("Couleurs descriptives relatives aux quartiers affichés · Cliquez sur les surfaces pour afficher les détails.")

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
