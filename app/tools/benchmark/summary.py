#!/usr/bin/env python3
"""One line per benchmark report: python tools/benchmark/summary.py data/bench/tune/*.json"""
import json, sys
print(f"{'config':22s} {'qr':>6s} {'phone':>6s} {'strm':>6s} {'bystd':>6s} {'qrGap':>6s} {'phGap':>6s} {'area%':>6s}")
for p in sys.argv[1:]:
    r = json.load(open(p))
    m = r['metrics']['all']
    pc = lambda k: float(m[k].split('%')[0]) if k in m else float('nan')
    gap = r.get('longest_exposure_ms', {})
    print(f"{p.split('/')[-1][:-5]:22s} {pc('qr_recall'):6.1f} {pc('phone_recall'):6.1f} {pc('streamer_visible'):6.1f} {pc('bystander_blurred'):6.1f} "
          f"{gap.get('qr', '-'):>6} {gap.get('phone', '-'):>6} {r['mean_mask_area_pct']:6.1f}")
