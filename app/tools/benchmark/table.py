#!/usr/bin/env python3
"""Print benchmark reports side by side: python tools/benchmark/table.py a.json b.json ..."""
import json, sys
rs = [json.load(open(p)) for p in sys.argv[1:]]
print('group/metric'.ljust(30) + ''.join(p.split('/')[-1][:-5].rjust(22) for p in sys.argv[1:]))
print('processing_fps'.ljust(30) + ''.join(str(r['processing_fps']).rjust(22) for r in rs))
print('mask_area_pct'.ljust(30) + ''.join(str(r['mean_mask_area_pct']).rjust(22) for r in rs))
for k in ('qr', 'phone'):
    print(f'longest_{k}_exposure_ms'.ljust(30) + ''.join(str(r.get('longest_exposure_ms', {}).get(k, '-')).rjust(22) for r in rs))
for g in rs[0]['metrics']:
    for m in rs[0]['metrics'][g]:
        print(f'{g}/{m}'.ljust(30) + ''.join(r['metrics'].get(g, {}).get(m, '-').rjust(22) for r in rs))
