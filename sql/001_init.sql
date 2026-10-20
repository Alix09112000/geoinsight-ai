CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS quartiers (
    id TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    geom geometry(MultiPolygon,4326) NOT NULL,
    source_url TEXT,
    imported_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_quartiers_geom ON quartiers USING GIST(geom);
