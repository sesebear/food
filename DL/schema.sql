-- schema.sql
-- Supabase schema for the City Congestion Tracker
-- Run this in the Supabase SQL Editor to set up your tables.

-- Locations table: represents intersections, road segments, or zones
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    zone TEXT NOT NULL,
    road_type TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL
);

-- Congestion readings table: time-series congestion measurements
CREATE TABLE IF NOT EXISTS congestion_readings (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    congestion_level INTEGER NOT NULL CHECK (congestion_level BETWEEN 0 AND 100),
    speed_mph DOUBLE PRECISION,
    volume INTEGER,
    delay_minutes DOUBLE PRECISION
);

-- Index for fast time-range queries
CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON congestion_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_readings_location ON congestion_readings(location_id);
CREATE INDEX IF NOT EXISTS idx_readings_level ON congestion_readings(congestion_level);

-- Enable Row Level Security (required by Supabase)
ALTER TABLE locations ENABLE ROW LEVEL SECURITY;
ALTER TABLE congestion_readings ENABLE ROW LEVEL SECURITY;

-- Allow anonymous reads for both tables
CREATE POLICY "Allow anonymous read locations" ON locations FOR SELECT USING (true);
CREATE POLICY "Allow anonymous read readings" ON congestion_readings FOR SELECT USING (true);

-- Allow inserts for seeding data
CREATE POLICY "Allow anonymous insert locations" ON locations FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous insert readings" ON congestion_readings FOR INSERT WITH CHECK (true);
