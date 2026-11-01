#!/usr/bin/env python3
"""A/B incremental box caching on replayed detections, with exact mask checks."""
import json
from pathlib import Path

import schedule_bench as bench
from cached_tracking import cd


class UncachedRedactor(cd.Redactor):
    def carry(self, box, start, end):
        box = list(map(float, box))
        for k in range(start + 1, end + 1):
            box = cd.move(box, self.disp[k], self.flow.pts, 1)
        for k in range(start, end, -1):
            box = cd.move(box, self.disp[k], self.flow.pts, -1)
        return [int(round(v)) for v in box]

results = {'baseline': [], 'cached': []}
for cached in (False, True, True, False):
    name = 'cached' if cached else 'baseline'
    result = bench.run(False, bench.Redactor if cached else UncachedRedactor)
    results[name].append(result)
    print(name, json.dumps(result), flush=True)
hashes = {r['mask_sha256'] for values in results.values() for r in values}
assert len(hashes) == 1, 'tracking optimization changed a mask'
path = Path(bench.CACHE / f'tracking-{bench.NAME}-{bench.START}.json')
path.write_text(json.dumps(results, indent=2))
