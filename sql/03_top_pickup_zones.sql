SELECT PULocationID AS zone_id,
       COUNT(*) AS trips,
       ROUND(AVG(fare_amount), 2) AS avg_fare
FROM lakehouse.nyc.yellow_trips
GROUP BY PULocationID
ORDER BY trips DESC
LIMIT 10;
