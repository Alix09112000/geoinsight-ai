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
            <span class="gi-globe">🌐</span>
            <div class="gi-brand">
              <div class="gi-brandname">GeoInsight <span>AI</span></div>
              <div class="gi-brandsub">Explorer le Québec</div>
            </div>
            <div class="gi-tagline">
              <strong>Comprendre les territoires. Éclairer les décisions.</strong>
              <small>Données géospatiales · Analyses · Visualisations · Intelligence territoriale</small>
            </div>
            <span class="gi-tag">QUÉBEC · PILOTE</span>
          </div>
        </div>
        """, unsafe_allow_html=True,
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
              densite=None, note=None):
    """Panneau de droite : uniquement des valeurs connues."""
    lines = [
        ('Niveau', niveau),
        ('Code officiel', code),
        ('Population (2021)', population),
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
        '<div class="gi-inspectorhead"><span>📍 Fiche territoriale</span>'
        '<span class="gi-live">DONNÉES RÉELLES</span></div>'
        '<div class="gi-inspectorbody"><div class="gi-inspectoreyebrow">TERRITOIRE SÉLECTIONNÉ</div>'
        '<h3>' + _safe(nom) + '</h3>' + rows + extra +
        '</div></div>',
        unsafe_allow_html=True,
    )


def info_unavailable():
    st.caption("Les indicateurs encore absents ne sont pas estimés ni simulés.")
