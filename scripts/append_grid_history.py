#!/usr/bin/env python3
"""Append the current Open-Meteo grid snapshot to a rolling history file.

grid_data.json is overwritten every hour, so there is no time series behind it.
The Historical Zones panel previously read weather_logs/alerts_24h.json, which
is built from the IMD station scrape. This produces the same shape from the
grid, aggregated by district, so the panel can be driven by Open-Meteo and the
IMD scrape is no longer required for it.

Unlike the station version, this carries all four MET levels, so the chart no
longer has to fall back to MET 6 for MET 4 and 5.

Run after generate_grid_data_openmeteo.py. Keeps HOURS_KEPT entries.
"""

import json
import os
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRID = os.path.join(ROOT, 'grid_data.json')
HIST = os.path.join(ROOT, 'weather_logs', 'grid_24h.json')
HOURS_KEPT = 24 * 31          # a month, so day/week/month views all have data
METS = [3, 4, 5, 6]
CONDS = ['shade', 'sun']


def district_zone_counts(points):
    """Worst zone per district per MET/sun, then counted."""
    worst = {}
    for p in points:
        d = p.get('district')
        if not d:
            continue
        key = (p.get('state'), d)
        slot = worst.setdefault(key, {})
        for met in METS:
            for cond in CONDS:
                cell = ((p.get('data') or {}).get(f'met{met}') or {}).get(cond)
                if not cell or cell.get('zone') is None:
                    continue
                k = f'met{met}_{cond}'
                if cell['zone'] > slot.get(k, 0):
                    slot[k] = cell['zone']

    counts = {f'met{m}_{c}_zone{z}': 0
              for m in METS for c in CONDS for z in range(1, 7)}
    # Per-state counts as well, so the chart can still filter by state without
    # storing a row per district (51 KB/entry vs 1.2 KB, ~37 MB vs 0.8 MB/month).
    by_state = {}
    for (state, _district), slot in worst.items():
        st = by_state.setdefault(state, {})
        for k, zone in slot.items():
            counts[f'{k}_zone{zone}'] += 1
            kk = f'{k}_zone{zone}'
            st[kk] = st.get(kk, 0) + 1
    return counts, by_state, len(worst)


def load_current_grid():
    """Prefer the look-ahead file for the current IST hour.

    grid_data.json carries generated_at (when the run fetched) but no
    valid_time (the hour the data is for), so recording from it stamps the
    history with 04:17 while the dashboard and map show 04:00 for the same
    data. The look-ahead files carry both, so the three panels agree.
    """
    from zoneinfo import ZoneInfo
    stamp = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y%m%d%H')
    hourly = os.path.join(ROOT, 'weather_logs', 'grid_hours', f'grid_{stamp}.json')
    if os.path.exists(hourly):
        with open(hourly) as fh:
            return json.load(fh)
    with open(GRID) as fh:
        return json.load(fh)


def main():
    grid = load_current_grid()

    counts, by_state, n_districts = district_zone_counts(grid.get('points', []))

    # Mean conditions, nationally and per state, so the chart's temperature and
    # humidity series do not need per-district rows.
    def means(points):
        t = [p['temp'] for p in points if p.get('temp') is not None]
        r = [p['rh'] for p in points if p.get('rh') is not None]
        return (round(sum(t) / len(t), 1) if t else None,
                round(sum(r) / len(r), 1) if r else None)

    pts = [p for p in grid.get('points', []) if p.get('district')]
    temp_mean, rh_mean = means(pts)
    by_state_means = {}
    for st in {p['state'] for p in pts}:
        t, r = means([p for p in pts if p['state'] == st])
        by_state_means[st] = {'temp': t, 'rh': r}
    alerts = sum(v for k, v in counts.items()
                 if k.startswith('met6_sun_zone') and k[-1] in '56')

    entry = {
        # The hour the data is FOR, not when the run fetched it, matching the
        # dashboard and the live map. grid_data.json carries no valid_time, so
        # fall back to generated_at for that case.
        'timestamp': (grid['metadata'].get('valid_time')
                      or grid['metadata'].get('generated_at')),
        'total_districts': n_districts,
        'alert_count': alerts,
        'zone_counts': counts,
        'zone_counts_by_state': by_state,
        'temp_mean': temp_mean,
        'rh_mean': rh_mean,
        'means_by_state': by_state_means,
        'is_nighttime': grid['metadata'].get('is_nighttime', False),
    }

    history = {'hourly_data': []}
    if os.path.exists(HIST):
        with open(HIST) as fh:
            history = json.load(fh)
    rows = history.get('hourly_data', [])

    # Replace rather than duplicate if this snapshot is already recorded.
    rows = [r for r in rows if r.get('timestamp') != entry['timestamp']]
    rows.append(entry)
    rows.sort(key=lambda r: r.get('timestamp') or '')

    cutoff = (datetime.now().astimezone() - timedelta(hours=HOURS_KEPT)).isoformat()
    rows = [r for r in rows if (r.get('timestamp') or '') >= cutoff][-HOURS_KEPT:]

    history['hourly_data'] = rows
    history['timestamp'] = entry['timestamp']
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    with open(HIST, 'w') as fh:
        json.dump(history, fh, separators=(',', ':'))

    print(f"grid_24h.json: {len(rows)} entries, latest "
          f"{entry['timestamp'][:16]} "
          f"({n_districts} districts, {alerts} in Zone 5/6 at EHI-6*)")


if __name__ == '__main__':
    main()
