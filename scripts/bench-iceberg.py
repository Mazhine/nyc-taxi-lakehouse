"""Phase 7: Iceberg features + measured before/after benchmarks (Trino only).

Steps (all timed, repeated, same machine):
  1. schema evolution (ADD + RENAME COLUMN): files count unchanged (no rewrite)
  2. time travel (FOR VERSION AS OF oldest snapshot) + rollback + restore
  3. compaction benchmark: query x5 BEFORE optimize, OPTIMIZE, query x5 AFTER
  4. partitioning benchmark: CTAS month-partitioned clone, same query x5 both
  5. full-build (CTAS slice) vs incremental (INSERT slice) timings + files
  6. expire_snapshots (1h retention, demo setting) + file counts
Outputs: experiments/phase7_*.json (raw, medians, config).
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import trino

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"
HOST, PORT = "localhost", 8080
REPEATS = 5

Q_MONTH = """
SELECT source_file, COUNT(*), AVG(total_amount)
FROM lakehouse.nyc.yellow_trips
WHERE tpep_pickup_datetime >= TIMESTAMP '2024-03-01'
  AND tpep_pickup_datetime < TIMESTAMP '2024-04-01'
GROUP BY source_file
"""


def conn():
    """Return a Trino connection (lakehouse catalog, nyc schema)."""
    return trino.dbapi.connect(
        host=HOST, port=PORT, user="lakehouse", catalog="lakehouse", schema="nyc"
    )


def run(sql: str) -> tuple[list[str], list[list]]:
    """Execute SQL; return (columns, rows)."""
    cur = conn().cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    return cols, [[str(v) for v in r] for r in cur.fetchall()]


def timed(sql: str, repeats: int = REPEATS) -> dict:
    """Run a query N times; return samples + median + stdev + last rows."""
    samples, rows = [], None
    for _ in range(repeats):
        start = time.perf_counter()
        _, rows = run(sql)
        samples.append(time.perf_counter() - start)
    out: dict = {
        "samples_s": samples,
        "median_s": statistics.median(samples),
        "repeats": repeats,
        "rows": rows,
    }
    if len(samples) > 1:
        out["stdev_s"] = statistics.stdev(samples)
    return out


def files_count(table: str) -> dict:
    """Return file count + bytes from the $files metadata table."""
    cat, schema, tbl = table.split(".")
    _, rows = run(f'SELECT COUNT(*), SUM(file_size_in_bytes) FROM {cat}.{schema}."{tbl}$files"')
    return {"data_files": int(rows[0][0]), "bytes": int(rows[0][1])}


def save(name: str, payload: dict) -> None:
    """Write an experiments JSON file and echo a one-liner."""
    (EXP / name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"saved {name}")


def main() -> None:
    """Run all Phase 7 demos and benchmarks."""
    report: dict = {
        "config": {"repeats": REPEATS, "engine": "trino-483-1-worker", "table_rows": 20015099}
    }

    # 1. schema evolution without rewrite
    before = files_count("lakehouse.nyc.yellow_trips")
    run("ALTER TABLE lakehouse.nyc.yellow_trips ADD COLUMN fare_per_mile DOUBLE")
    run("ALTER TABLE lakehouse.nyc.yellow_trips RENAME COLUMN tip_amount TO tip_amt")
    _, cols = run("SHOW COLUMNS FROM lakehouse.nyc.yellow_trips")
    after = files_count("lakehouse.nyc.yellow_trips")
    report["schema_evolution"] = {
        "added": "fare_per_mile",
        "renamed": "tip_amount->tip_amt",
        "columns": [c[0] for c in cols],
        "files_before": before,
        "files_after": after,
        "no_rewrite": before == after,
    }
    print("evolution: files unchanged =", before == after)

    # 2. time travel + rollback + restore
    _, snaps = run(
        'SELECT snapshot_id FROM lakehouse.nyc."yellow_trips$snapshots" ORDER BY committed_at'
    )
    oldest, latest = snaps[0][0], snaps[-1][0]
    _, old_count = run(
        f"SELECT COUNT(*) FROM lakehouse.nyc.yellow_trips FOR VERSION AS OF {oldest}"
    )
    run(f"CALL lakehouse.system.rollback_to_snapshot('nyc', 'yellow_trips', {oldest})")
    _, rolled = run("SELECT COUNT(*) FROM lakehouse.nyc.yellow_trips")
    run(f"CALL lakehouse.system.rollback_to_snapshot('nyc', 'yellow_trips', {latest})")
    _, restored = run("SELECT COUNT(*) FROM lakehouse.nyc.yellow_trips")
    report["time_travel"] = {
        "oldest_snapshot": oldest,
        "latest_snapshot": latest,
        "count_at_oldest": int(old_count[0][0]),
        "count_after_rollback": int(rolled[0][0]),
        "count_after_restore": int(restored[0][0]),
    }
    print("time travel:", report["time_travel"])

    # 3. compaction benchmark
    bench_before = timed(Q_MONTH)
    files_before = files_count("lakehouse.nyc.yellow_trips")
    t0 = time.perf_counter()
    _, opt = run(
        "ALTER TABLE lakehouse.nyc.yellow_trips EXECUTE optimize(file_size_threshold => '64MB')"
    )
    optimize_s = time.perf_counter() - t0
    bench_after = timed(Q_MONTH)
    files_after = files_count("lakehouse.nyc.yellow_trips")
    report["compaction"] = {
        "query": "march-2024 slice agg",
        "before": bench_before,
        "after": bench_after,
        "files_before": files_before,
        "files_after": files_after,
        "optimize_s": optimize_s,
        "optimize_result": opt,
    }
    save("phase7_compaction.json", report["compaction"])

    # 4. partitioning benchmark (CTAS clone, then same query both sides)
    t0 = time.perf_counter()
    run("DROP TABLE IF EXISTS lakehouse.nyc.yellow_trips_part")
    run(
        "CREATE TABLE lakehouse.nyc.yellow_trips_part "
        "WITH (partitioning = ARRAY['month(tpep_pickup_datetime)']) "
        "AS SELECT * FROM lakehouse.nyc.yellow_trips"
    )
    ctas_s = time.perf_counter() - t0
    q_part = Q_MONTH.replace("lakehouse.nyc.yellow_trips", "lakehouse.nyc.yellow_trips_part")
    report["partitioning"] = {
        "ctas_partitioned_s": ctas_s,
        "unpartitioned": timed(Q_MONTH),
        "partitioned": timed(q_part),
        "files_partitioned": files_count("lakehouse.nyc.yellow_trips_part"),
    }
    save("phase7_partitioning.json", report["partitioning"])

    # 5. full build vs incremental append (one-month slices)
    t0 = time.perf_counter()
    run("DROP TABLE IF EXISTS lakehouse.nyc.bench_slice")
    run(
        "CREATE TABLE lakehouse.nyc.bench_slice AS SELECT * FROM lakehouse.nyc.yellow_trips "
        "WHERE source_file = 'yellow_tripdata_2024-01'"
    )
    full_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    run(
        "INSERT INTO lakehouse.nyc.bench_slice SELECT * FROM lakehouse.nyc.yellow_trips "
        "WHERE source_file = 'yellow_tripdata_2024-02'"
    )
    incr_s = time.perf_counter() - t0
    _, counts = run(
        "SELECT source_file, COUNT(*) FROM lakehouse.nyc.bench_slice GROUP BY source_file"
    )
    report["full_vs_incremental"] = {
        "full_ctas_2024_01_s": full_s,
        "incremental_insert_2024_02_s": incr_s,
        "bench_contents": counts,
        "files_bench": files_count("lakehouse.nyc.bench_slice"),
    }
    save("phase7_full_vs_incremental.json", report["full_vs_incremental"])

    # 6. expire snapshots (1h demo retention)
    _, snaps_before = run('SELECT COUNT(*) FROM lakehouse.nyc."yellow_trips$snapshots"')
    t0 = time.perf_counter()
    _, exp_res = run(
        "ALTER TABLE lakehouse.nyc.yellow_trips "
        "EXECUTE expire_snapshots(retention_threshold => '1h')"
    )
    expire_s = time.perf_counter() - t0
    _, snaps_after = run('SELECT COUNT(*) FROM lakehouse.nyc."yellow_trips$snapshots"')
    report["expire_snapshots"] = {
        "snapshots_before": int(snaps_before[0][0]),
        "snapshots_after": int(snaps_after[0][0]),
        "result": exp_res,
        "expire_s": expire_s,
        "files_now": files_count("lakehouse.nyc.yellow_trips"),
    }
    save("phase7_expire.json", report["expire_snapshots"])

    report["snapshots_for_reference"] = {"note": "see phase5_04_snapshots.json"}
    save("phase7_report.json", report)
    print(json.dumps({k: "ok" for k in report}, indent=2))


if __name__ == "__main__":
    main()
