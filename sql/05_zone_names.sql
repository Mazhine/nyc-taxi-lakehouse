SELECT z.Zone AS pickup_zone,
       z.Borough AS borough,
       COUNT(*) AS trips,
       ROUND(AVG(t.fare_amount), 2) AS avg_fare
FROM lakehouse.nyc.yellow_trips t
JOIN lakehouse.nyc.taxi_zones z ON t.PULocationID = z.location_id
GROUP BY z.Zone, z.Borough
ORDER BY trips DESC
LIMIT 10;
