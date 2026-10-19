"""Extract the JSON summary block from a Spark job log into a ``.json`` file.

When a Spark job runs on Kubernetes, the pod log mixes Spark's own INFO lines
with the JSON summary printed by our job. This one-off utility recovers the
JSON payload from the raw log so the Phase 4 evidence files are machine
readable. It is not part of the pipeline; it was used during development.
"""

import glob
import json
import re

for path in sorted(glob.glob("experiments/phase4_*.raw.log")):
    text = open(path, encoding="utf-8").read()
    # Ingestion runs start with {"source_file": ...}; count runs with {"table": ...}
    match = re.search(r"\{\s*\n\s*\"source_file\"", text)
    if match:
        summary, _ = json.JSONDecoder().raw_decode(text[match.start() :])
        out = path.replace(".raw.log", ".json")
        json.dump(summary, open(out, "w"), indent=2)
        print(
            out,
            "input=",
            summary["input_rows"],
            "valid=",
            summary["valid_rows"],
            "quar=",
            summary["quarantined_rows"],
        )
        continue
    match = re.search(r"\{\s*\n\s*\"table\"", text)
    if match:
        summary, _ = json.JSONDecoder().raw_decode(text[match.start() :])
        out = path.replace(".raw.log", ".json")
        json.dump(summary, open(out, "w"), indent=2)
        print(out, "total=", summary["total"])
        continue
    print("skip (no summary):", path)
