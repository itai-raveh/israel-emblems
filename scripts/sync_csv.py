#!/usr/bin/env python3
"""
sync_csv.py — Sync municipalities.csv status with actual files in the repo.

For each municipality:
- If an SVG exists in emblems/svg/ → status = found-svg
- If a PNG exists in emblems/png/ (but no SVG) → status = found-png  
- If neither exists → keep existing status (not-found, wrong-file, etc.)

Run:
    python3 sync_csv.py --repo ~/Documents/GitHub/israel-emblems

This overwrites municipalities.csv in place. Commit and push after.
"""

import re, argparse
import pandas as pd
from pathlib import Path

def get_id(filename):
    return filename.split('__')[0] if '__' in filename else None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    args = parser.parse_args()

    repo    = Path(args.repo)
    svg_dir = repo / 'emblems' / 'svg'
    png_dir = repo / 'emblems' / 'png'
    csv_path = repo / 'data' / 'municipalities.csv'

    df = pd.read_csv(csv_path, dtype=str).fillna('')

    # Build sets of IDs that have files
    svg_ids = {get_id(f.stem) for f in svg_dir.iterdir() if f.is_file() and '__' in f.name}
    png_ids = {get_id(f.stem) for f in png_dir.iterdir() if f.is_file() and '__' in f.name}
    svg_ids.discard(None)
    png_ids.discard(None)

    changes = []
    for i, row in df.iterrows():
        muni_id = row['id']
        old_status = row['status']

        if muni_id in svg_ids:
            new_status = 'found-svg'
        elif muni_id in png_ids:
            new_status = 'found-png'
        else:
            new_status = old_status  # keep existing

        if new_status != old_status:
            changes.append((muni_id, row.get('name_en',''), old_status, new_status))
            df.at[i, 'status'] = new_status

    # Report
    print(f"\n{'='*60}")
    print(f"sync_csv.py — {len(changes)} status changes")
    print(f"{'='*60}\n")

    if changes:
        for muni_id, name_en, old, new in sorted(changes):
            arrow = '↑' if 'svg' in new or ('png' in new and 'not' in old) else '↓'
            print(f"  {arrow} {muni_id:25s} {old:15s} → {new}")
    else:
        print("  No changes needed — CSV is already in sync.")

    # Summary counts
    counts = df['status'].value_counts()
    print(f"\n{'='*60}")
    print(f"Updated counts:")
    for s, c in counts.items():
        print(f"  {s:20s}: {c}")
    print(f"{'='*60}\n")

    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"Saved: {csv_path}")
    print("Now commit and push in GitHub Desktop.")

if __name__ == '__main__':
    main()
