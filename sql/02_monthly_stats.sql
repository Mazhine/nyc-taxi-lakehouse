-- Query 02: per-month volume and averages.
-- source_file is the ledger column, so it maps 1:1 to an ingested month;
-- comparing these counts with the ingest summaries proves nothing was lost.
SELECT source_file,
       COUNT(*) AS trips,
       ROUND(AVG(fare_amount), 2) AS avg_fare,
       ROUND(AVG(trip_distance), 2) AS avg_distance_mi,
       ROUND(AVG(total_amount), 2) AS avg_total
FROM lakehouse.nyc.yellow_trips
GROUP BY source_file
ORDER BY source_file;
