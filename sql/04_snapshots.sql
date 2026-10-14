SELECT snapshot_id, committed_at, operation, summary
FROM lakehouse.nyc."yellow_trips$snapshots"
ORDER BY committed_at;
