-- Query 05: top 10 pickup zones by trip count, with readable names.
-- Joins the fact table to the taxi_zones reference/dimension table on the raw
-- location id, which is why the zones table must be loaded first.
SELECT z.Zone AS pickup_zone,
       z.Borough AS borough,
       COUNT(*) AS trips,
       ROUND(AVG(t.fare_amount), 2) AS avg_fare
FROM lakehouse.nyc.yellow_trips t
JOIN lakehouse.nyc.taxi_zones z ON t.PULocationID = z.location_id
GROUP BY z.Zone, z.Borough
ORDER BY trips DESC
LIMIT 10;
