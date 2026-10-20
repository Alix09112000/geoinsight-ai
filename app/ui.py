"""Interface visuelle GeoInsight AI — composants de présentation sans données inventées."""
from html import escape

import folium
import streamlit as st


def _safe(value):
    return escape(str(value), quote=True)


def header():
    """Bandeau compact inspiré de la maquette approuvée."""
    st.markdown(
        """
        <div class="gi-topbar">
          <div class="gi-topline">
            <div class="gi-brand">
              <div class="gi-brandname">GeoInsight <span>AI</span></div>
              <div class="gi-brandsub">Explorer le Québec</div>
            </div>
            <div class="gi-tagline">
              <strong>Comprendre les territoires. Éclairer les décisions.</strong>
              <small>Données géospatiales · Analyses · Visualisations · Intelligence territoriale</small>
            </div>
            <span class="gi-tag">QUÉBEC · BI GÉOSPATIALE</span>
          </div>
        </div>
        """, unsafe_allow_html=True,
    )


def metric_card(icon, title, value, subtitle="", tone="blue"):
    """KPI sobre et sourcé : la fonction n'invente jamais de chiffres."""
    if tone not in ("blue", "cyan", "green", "violet"):
        tone = "blue"
    st.markdown(
        '<div class="gi-kpi gi-kpi-' + tone + '">'
        '<div class="gi-kpi-icon">' + _safe(icon) + '</div>'
        '<div class="gi-kpi-content">'
        '<span class="gi-kpi-title">' + _safe(title) + '</span>'
        '<strong>' + _safe(value) + '</strong>'
        '<small>' + _safe(subtitle) + '</small>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def section(label, note=""):
    st.markdown(
        '<div class="gi-section"><strong>' + _safe(label) + '</strong>' +
        ('<span>' + _safe(note) + '</span>' if note else '') +
        '</div>',
        unsafe_allow_html=True,
    )


def map_object(location, zoom, fond):
    """Fond plan ou imagerie satellite ; pas de mode 3D simulé."""
    carte = folium.Map(
        location=location, zoom_start=zoom, tiles=None,
        control_scale=True, zoom_control=True, prefer_canvas=True
    )
    if fond == "Satellite":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
                  "World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri, Maxar, Earthstar Geographics, and the GIS User Community",
            name="Satellite — Esri World Imagery",
            overlay=False, control=True,
        ).add_to(carte)
    else:
        folium.TileLayer("OpenStreetMap", name="Plan — OpenStreetMap").add_to(carte)
    return carte


def inspector(nom, niveau, code=None, population=None, superficie=None,
              densite=None, note=None, population_annee=2021):
    """Panneau de droite : uniquement des valeurs connues."""
    lines = [
        ('Niveau', niveau),
        ('Code officiel', code),
        (f'Population ({population_annee})', population),
        ('Superficie géographique', superficie),
        ('Densité', densite),
    ]
    rows = "".join(
        '<div class="gi-detailrow"><span>' + _safe(label) + '</span>'
        '<strong>' + _safe(value) + '</strong></div>'
        for label, value in lines if value is not None
    )
    extra = '<p class="gi-panelnote">' + _safe(note) + '</p>' if note else ''
    st.markdown(
        '<div class="gi-inspector">'
        '<div class="gi-inspectorhead"><span>Fiche territoriale</span>'
        '<span class="gi-live">DONNÉES RÉELLES</span></div>'
        '<div class="gi-inspectorbody"><div class="gi-inspectoreyebrow">TERRITOIRE SÉLECTIONNÉ</div>'
        '<h3>' + _safe(nom) + '</h3>' + rows + extra +
        '</div></div>',
        unsafe_allow_html=True,
    )


def info_unavailable():
    st.caption("Les indicateurs encore absents ne sont pas estimés ni simulés.")


def legend_choropleth(title, minimum, maximum):
    """Légende compacte hors de la carte, avec valeurs lisibles sans graduations superposées."""
    if minimum is None or maximum is None or minimum >= maximum:
        return
    def fmt(value):
        return f"{value:,.0f}".replace(",", " ")
    middle = (minimum + maximum) / 2
    st.markdown(
        '<div class="gi-legend">'
        '<div class="gi-legendheading">' + _safe(title) + '</div>'
        '<div class="gi-legendbar"></div>'
        '<div class="gi-legendlabels">'
        '<span>' + _safe(fmt(minimum)) + '</span>'
        '<span>' + _safe(fmt(middle)) + '</span>'
        '<span>' + _safe(fmt(maximum)) + '</span>'
        '</div></div>', unsafe_allow_html=True,
    )


def ajouter_fiche_sur_carte(carte, nom, niveau, code=None, population=None,
                           population_annee=2025, superficie=None, densite=None,
                           source="Données territoriales disponibles"):
    """Fiche fixe dans l'iframe Folium, inspirée de la maquette originale.

    Éléments purement informatifs : aucune action ou chiffre simulé.
    Tous les textes des données externes sont échappés.
    """
    lignes = [("Échelle", niveau), ("Code", code),
              (f"Population ({population_annee})", population),
              ("Superficie", superficie), ("Densité", densite)]
    details = "".join(
        '<div class="gi-map-detail"><span>' + _safe(label) + '</span>'
        '<strong>' + _safe(valeur) + '</strong></div>'
        for label, valeur in lignes if valeur is not None
    )
    contenu = (
        '<style>'
        '.gi-map-panel{position:fixed;right:14px;top:16px;z-index:9999;'
        'width:282px;max-height:calc(100vh - 35px);overflow:auto;'
        'background:#f3f2f2;border:2px solid rgba(32,30,29,.4);border-radius:0;'
        'box-shadow:0 8px 24px rgba(32,30,29,.18);font-family:Archivo,system-ui,sans-serif;}'
        '.gi-map-top{background:#095797;'
        'color:#f3f2f2;font-size:14px;font-weight:700;padding:14px 15px;}'
        '.gi-map-body{padding:16px 14px;color:#201e1d;}'
        '.gi-map-sub{font-size:10px;letter-spacing:1px;color:#083f73;font-weight:bold;}'
        '.gi-map-title{font-size:20px;line-height:1.22;margin:10px 0 17px;'
        'font-weight:800;overflow-wrap:anywhere;}'
        '.gi-map-detail{display:flex;justify-content:space-between;gap:8px;'
        'padding:10px 0;border-bottom:1px solid rgba(32,30,29,.18);font-size:12px;}'
        '.gi-map-detail span{color:#5b5857;}'
        '.gi-map-detail strong{text-align:right;color:#201e1d;overflow-wrap:anywhere;}'
        '.gi-map-source{color:#5b5857;line-height:1.45;font-size:11px;margin-top:15px;}'
        '@media(max-width:720px){.gi-map-panel{width:190px;right:8px;top:10px;}'
        '.gi-map-body{padding:10px}.gi-map-title{font-size:15px}}'
        '</style>'
        '<aside class="gi-map-panel" aria-label="Fiche du territoire">'
        '<div class="gi-map-top">Fiche territoriale</div>'
        '<div class="gi-map-body"><div class="gi-map-sub">TERRITOIRE SÉLECTIONNÉ</div>'
        '<div class="gi-map-title">' + _safe(nom) + '</div>'
        + details +
        '<div class="gi-map-source">' + _safe(source) + '</div>'
        '</div></aside>'
    )
    carte.get_root().html.add_child(folium.Element(contenu))
    return carte
