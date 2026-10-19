-- Query 03: top 10 pickup zones by trip count (raw location ids).
-- Zone ids are used here; sql/05 resolves them to human-readable names.
SELECT PULocationID AS zone_id,
       COUNT(*) AS trips,
       ROUND(AVG(fare_amount), 2) AS avg_fare
FROM lakehouse.nyc.yellow_trips
GROUP BY PULocationID
ORDER BY trips DESC
LIMIT 10;
