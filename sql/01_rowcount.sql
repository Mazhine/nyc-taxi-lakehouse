-- Query 01: total number of trusted rows in the fact table.
-- This is the headline number checked by scripts/verify-results.py
-- (must equal the sum of valid_rows across the ingest summaries).
SELECT COUNT(*) AS total_rows FROM lakehouse.nyc.yellow_trips;
