"""Extract JSON summary blocks from spark job logs into JSON files."""

import glob
import json
import re

for path in sorted(glob.glob("experiments/phase4_*.raw.log")):
    text = open(path, encoding="utf-8").read()
    match = re.search(r"\{\s*\n\s*\"source_file\"", text)
    if match:
        summary, _ = json.JSONDecoder().raw_decode(text[match.start():])
        out = path.replace(".raw.log", ".json")
        json.dump(summary, open(out, "w"), indent=2)
        print(out, "input=", summary["input_rows"], "valid=", summary["valid_rows"],
              "quar=", summary["quarantined_rows"])
        continue
    match = re.search(r"\{\s*\n\s*\"table\"", text)
    if match:
        summary, _ = json.JSONDecoder().raw_decode(text[match.start():])
        out = path.replace(".raw.log", ".json")
        json.dump(summary, open(out, "w"), indent=2)
        print(out, "total=", summary["total"])
        continue
    print("skip (no summary):", path)
