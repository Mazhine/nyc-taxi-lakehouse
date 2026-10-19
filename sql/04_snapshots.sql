-- Query 04: Iceberg snapshot history of the fact table.
-- One snapshot per append; ids/timestamps change on every rebuild, so this is
-- verified structurally (count + operation) rather than byte-for-byte.
SELECT snapshot_id, committed_at, operation, summary
FROM lakehouse.nyc."yellow_trips$snapshots"
ORDER BY committed_at;
