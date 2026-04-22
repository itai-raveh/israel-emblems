#!/usr/bin/env python3
"""
Run from the repo root:
  python3 check_transparency.py

Outputs two files:
  no_transparency.txt  — PNGs with no alpha channel (solid white background)
  has_transparency.txt — PNGs that already have transparency
"""

import os
from PIL import Image

PNG_DIRS = ["emblems/png", "emblems/svg"]
results_no_alpha = []
results_has_alpha = []

def has_transparency(path):
    try:
        img = Image.open(path)
        if img.mode == "RGBA":
            # Check if any pixel has alpha < 255
            r, g, b, a = img.split()
            return a.getextrema()[0] < 255
        elif img.mode == "LA":
            l, a = img.split()
            return a.getextrema()[0] < 255
        elif img.mode == "P":
            # Palette mode — check for transparency info
            return "transparency" in img.info
        else:
            # RGB, L, etc — no alpha channel at all
            return False
    except Exception as e:
        print(f"  ERROR {path}: {e}")
        return None

total = 0
for d in PNG_DIRS:
    if not os.path.isdir(d):
        continue
    for fname in sorted(os.listdir(d)):
        if not fname.lower().endswith(".png"):
            continue
        path = os.path.join(d, fname)
        result = has_transparency(path)
        total += 1
        if result is True:
            results_has_alpha.append(fname)
        elif result is False:
            results_no_alpha.append(fname)

print(f"\nChecked {total} PNGs")
print(f"  With transparency:    {len(results_has_alpha)}")
print(f"  Without transparency: {len(results_no_alpha)}")

with open("no_transparency.txt", "w") as f:
    f.write("\n".join(results_no_alpha))

with open("has_transparency.txt", "w") as f:
    f.write("\n".join(results_has_alpha))

print("\nSaved: no_transparency.txt and has_transparency.txt")
print("\nFiles WITHOUT transparency (need fixing):")
for fname in results_no_alpha:
    print(" ", fname)
