#!/usr/bin/env python3
"""
download_crwflags.py
====================
Downloads Palestinian municipal emblems from crwflags.com.
Image URLs derived from the page structure: fotw/images/p/{slug}.gif

Run from repo root:
    python3 scripts/download_crwflags.py
"""

import os, time
import requests

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.crwflags.com/fotw/flags/ps_muni.html",
})

PNG_DIR = "emblems/png"
os.makedirs(PNG_DIR, exist_ok=True)

# id → crwflags image URL
# Pattern: https://www.crwflags.com/fotw/images/p/{slug}.gif
CRWFLAGS_IMAGES = {
    "ps-wb-ramallah":               "https://www.crwflags.com/fotw/images/p/ps-rama.gif",
    "ps-wb-nablus":                 "https://www.crwflags.com/fotw/images/p/ps-nabl.gif",
    "ps-wb-hebron":                 "https://www.crwflags.com/fotw/images/p/ps-hebr.gif",
    "ps-wb-jericho":                "https://www.crwflags.com/fotw/images/p/ps-jeri.gif",
    "ps-wb-dura":                   "https://www.crwflags.com/fotw/images/p/ps-dura.gif",
    "ps-wb-yatta":                  "https://www.crwflags.com/fotw/images/p/ps-yata.gif",
    "ps-gz-gaza-city":              "https://www.crwflags.com/fotw/images/p/ps-gaza.gif",
    "ps-gz-khan-yunis":             "https://www.crwflags.com/fotw/images/p/ps-yuni.gif",
    "ps-gz-rafah":                  "https://www.crwflags.com/fotw/images/p/ps-rafa.gif",
    "ps-gz-jabalia":                "https://www.crwflags.com/fotw/images/p/ps-jaba.gif",
    "ps-wb-al-bireh":               "https://www.crwflags.com/fotw/images/p/ps-bire.gif",
    "ps-wb-beit-jala":              "https://www.crwflags.com/fotw/images/p/ps-jala.gif",
    "ps-wb-beit-sahour":            "https://www.crwflags.com/fotw/images/p/ps-beit.gif",
    "ps-wb-beit-ummar":             "https://www.crwflags.com/fotw/images/p/ps-umma.gif",
    "ps-wb-beitunia":               "https://www.crwflags.com/fotw/images/p/ps-unia.gif",
    "ps-gz-beit-hanoun":            "https://www.crwflags.com/fotw/images/p/ps-bhan.gif",
    "ps-gz-beit-lahiya":            "https://www.crwflags.com/fotw/images/p/ps-lahi.gif",
    "ps-gz-bani-suheila":           "https://www.crwflags.com/fotw/images/p/ps-suha.gif",
    "ps-wb-idhna":                  "https://www.crwflags.com/fotw/images/p/ps-idhn.gif",
    "ps-gz-deir-al-balah":          "https://www.crwflags.com/fotw/images/p/ps-bala.gif",
    "ps-gz-abasan-al-kabira":       "https://www.crwflags.com/fotw/images/p/ps-abas.gif",
    "ps-wb-qabatya":                "https://www.crwflags.com/fotw/images/p/ps-qaba.gif",
    "ps-wb-halhul":                 "https://www.crwflags.com/fotw/images/p/ps-halh.gif",
    "ps-wb-tulkarm":                "https://www.crwflags.com/fotw/images/p/ps-tulk.gif",
    "ps-wb-sair":                   "https://www.crwflags.com/fotw/images/p/ps-sier.gif",
    "ps-wb-qalqilya":               "https://www.crwflags.com/fotw/images/p/ps-qalq.gif",
    # Also check these that may have crwflags entries
    "ps-wb-salfit":                 "https://www.crwflags.com/fotw/images/p/ps-salf.gif",
    "ps-wb-tubas":                  "https://www.crwflags.com/fotw/images/p/ps-tuba.gif",
}

ok, skipped, failed = 0, 0, 0

for eid, url in CRWFLAGS_IMAGES.items():
    # Check if already have a good file
    existing = [
        os.path.join("emblems/svg", f"{eid}-COA.svg"),
        os.path.join("emblems/png", f"{eid}-COA.png"),
        os.path.join("emblems/png", f"{eid}-COA.gif"),
    ]
    if any(os.path.exists(p) for p in existing):
        print(f"⏭  {eid} — already have file")
        skipped += 1
        continue

    dest = os.path.join(PNG_DIR, f"{eid}-COA.gif")
    try:
        r = SESSION.get(url, timeout=15, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(4096):
                f.write(chunk)
        size = os.path.getsize(dest)
        # Sanity check — if < 500 bytes it's probably a 404 page or placeholder
        if size < 500:
            os.remove(dest)
            print(f"✗  {eid} — file too small ({size}B), likely 404")
            failed += 1
        else:
            print(f"✅ {eid} — {size//1024}KB → {dest}")
            ok += 1
    except Exception as e:
        print(f"❌ {eid} — {e}")
        failed += 1
    time.sleep(1.0)

print(f"\n{'='*50}")
print(f"Downloaded : {ok}")
print(f"Skipped    : {skipped}")
print(f"Failed     : {failed}")
print(f"\nNext:")
print(f"  git add emblems/")
print(f"  git commit -m 'Add Palestinian emblems from crwflags ({ok} files)'")
print(f"  git push")
