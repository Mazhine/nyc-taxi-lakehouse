SELECT source_file,
       COUNT(*) AS trips,
       ROUND(AVG(fare_amount), 2) AS avg_fare,
       ROUND(AVG(trip_distance), 2) AS avg_distance_mi,
       ROUND(AVG(total_amount), 2) AS avg_total
FROM lakehouse.nyc.yellow_trips
GROUP BY source_file
ORDER BY source_file;
