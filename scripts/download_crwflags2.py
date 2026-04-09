#!/usr/bin/env python3
"""
download_crwflags2.py — Round 2
================================
Fixes: Yatta had wrong filename (ps-yatta not ps-yata)
Adds: remaining cities not yet downloaded
Also fixes the sort bug from fix_emblems.py by re-running
Arabic wiki scrape with corrected scoring.

Run from repo root:
    python3 scripts/download_crwflags2.py
"""

import os, time, re, urllib.parse
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.crwflags.com/fotw/flags/ps_muni.html",
})

PNG_DIR = "emblems/png"
SVG_DIR = "emblems/svg"
os.makedirs(PNG_DIR, exist_ok=True)
os.makedirs(SVG_DIR, exist_ok=True)

# ── Part 1: crwflags corrections + additions ──────────────────────────────────

CRWFLAGS = {
    # Corrections
    "ps-wb-yatta":      "https://www.crwflags.com/fotw/images/p/ps-yatta.gif",  # was ps-yata
    # Ones not yet tried
    "ps-wb-jenin":      None,  # crwflags has no page for Jenin
    "ps-wb-tubas":      None,  # crwflags has no page for Tubas
    "ps-wb-salfit":     None,  # crwflags has no page for Salfit
}

def already_have(eid):
    for folder, ext in [(SVG_DIR,"svg"),(PNG_DIR,"png"),(PNG_DIR,"gif")]:
        if os.path.exists(os.path.join(folder, f"{eid}-COA.{ext}")):
            return True
    return False

def download_gif(eid, url):
    dest = os.path.join(PNG_DIR, f"{eid}-COA.gif")
    r = SESSION.get(url, timeout=15, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(4096): f.write(chunk)
    size = os.path.getsize(dest)
    if size < 500:
        os.remove(dest)
        return None
    return size

print("=== Part 1: crwflags corrections ===\n")
for eid, url in CRWFLAGS.items():
    if already_have(eid):
        print(f"⏭  {eid} — already have")
        continue
    if url is None:
        print(f"✗  {eid} — no crwflags page")
        continue
    try:
        size = download_gif(eid, url)
        if size:
            print(f"✅ {eid} — {size//1024}KB")
        else:
            print(f"✗  {eid} — file too small (404?)")
    except Exception as e:
        print(f"❌ {eid} — {e}")
    time.sleep(1)

# ── Part 2: Arabic Wikipedia with fixed scoring ───────────────────────────────
# The bug was candidates.sort(reverse=True) on list of (int, Tag) tuples —
# Python 3 can't compare Tags. Fix: sort only by score using key=.

BAD = ["flag","map","location","locator","skyline","panorama","mosque","church",
       "street","road","aerial","satellite","cemetery","cropped","red_pog",
       "مساء","Red_pog"]
GOOD = ["seal","coat","coa","emblem","logo","شعار","خاتم","ختم",
        "municipal","municipality","official logo","official seal","badge"]

def score_img(img, name_en, name_ar):
    src = img.get("src","")
    if "Red_pog" in src or "red_pog" in src.lower(): return -99
    alt = img.get("alt","").lower()
    combined = (src+" "+alt).lower()
    if any(b.lower() in combined for b in BAD): return -1
    score = sum(5 for g in GOOD if g in combined)
    if name_en and name_en.lower() in combined: score += 3
    if name_ar:
        score += sum(2 for p in name_ar.split() if len(p)>2 and p in combined)
    if "/commons/" in src: score += 2
    try:
        if int(img.get("width",999)) < 200: score += 1
    except: pass
    return score

def extract_emblem(soup, name_en, name_ar):
    infobox = (soup.find("table", class_=re.compile(r"infobox")) or
               soup.find("table", class_=re.compile(r"vcard")))
    if not infobox: return None
    scored = []
    for img in infobox.find_all("img"):
        src = img.get("src","")
        if not src or "1x1" in src: continue
        s = score_img(img, name_en, name_ar)
        if s >= 1: scored.append((s, id(img), img))  # id() breaks Tag tie
    if not scored: return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][2]

def resolve_url(img):
    src = img.get("src","")
    srcset = img.get("srcset","")
    if srcset:
        last = srcset.strip().split(",")[-1].strip().split()[0]
        if last: src = last
    if src.startswith("//"): src = "https:"+src
    m = re.search(
        r"(upload\.wikimedia\.org/wikipedia/[^/]+)/thumb/([a-f0-9]/[a-f0-9]{2}/([^/]+))/\d+px-",
        src)
    if m:
        base, hashpath, filename = m.group(1), m.group(2), unquote(m.group(3))
        ext = filename.rsplit(".",1)[-1].lower()
        if ext in ("tif","tiff"): return src, filename.rsplit(".",1)[0]+".png"
        return f"https://{base}/{hashpath}", filename
    return src, unquote(src.rsplit("/",1)[-1].split("?")[0])

def try_ar_wiki(name_ar, name_en, name_ar_full):
    slug = urllib.parse.quote(name_ar.replace(" ","_"), safe="")
    url = f"https://ar.wikipedia.org/wiki/{slug}"
    try:
        r = SESSION.get(url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        return extract_emblem(soup, name_en, name_ar_full)
    except Exception as e:
        print(f"    [ar] {e}")
        return None

def save_img(eid, img):
    try:
        url, filename = resolve_url(img)
    except Exception as e:
        return f"url-error: {e}"
    ext = filename.rsplit(".",1)[-1].lower() if "." in filename else "png"
    dest = os.path.join(SVG_DIR, f"{eid}-COA.svg") if ext=="svg" \
           else os.path.join(PNG_DIR, f"{eid}-COA.{'gif' if ext=='gif' else 'png'}")
    try:
        r = SESSION.get(url, timeout=30, stream=True)
        r.raise_for_status()
        with open(dest,"wb") as f:
            for chunk in r.iter_content(8192): f.write(chunk)
        size = os.path.getsize(dest)
        print(f"    ✅ {ext.upper()} ({size//1024}KB) ← {filename[:55]}")
        return "ok"
    except Exception as e:
        return f"download-error: {e}"

# Cities still missing that need Arabic wiki retry
import csv
rows = {r["id"]: r for r in csv.DictReader(open("data/palestinian_municipalities.csv", encoding="utf-8"))}

STILL_MISSING = [
    # Major cities not found via EN wiki, not on crwflags
    "ps-wb-jenin", "ps-wb-tubas", "ps-wb-salfit",
    "ps-wb-ramallah-and-al-bireh-governorate",
    # Villages where AR wiki has emblems
    "ps-wb-arraba", "ps-wb-aqraba", "ps-wb-asira-ash-shamaliyya",
    "ps-wb-beit-dajan", "ps-wb-burin", "ps-wb-salim", "ps-wb-sebastia",
    "ps-wb-beit-ur-al-fauqa", "ps-wb-beit-ur-al-tahta",
    "ps-wb-al-ubeidiyya", "ps-wb-huwwara",
    # Gaza
    "ps-gz-al-maghazi", "ps-gz-al-nuseirat", "ps-gz-abasan-al-jadida",
    "ps-gz-khuzaa",
    # Rate-limited ones that were real emblems (not Red_pog)
    "ps-wb-al-khader", "ps-wb-taffuh", "ps-wb-silwad",
    "ps-wb-turmusayya", "ps-wb-bruqin", "ps-wb-kafr-ad-dik",
    "ps-wb-tayasir", "ps-wb-attil", "ps-wb-beit-lid", "ps-wb-beit-rima",
]

print("\n=== Part 2: Arabic Wikipedia retry (fixed) ===\n")
for eid in STILL_MISSING:
    if already_have(eid): continue
    row = rows.get(eid)
    if not row: continue
    name_en = row["name_en"]
    name_ar = row.get("name_ar","")
    if not name_ar:
        print(f"  ✗  {name_en}: no Arabic name")
        continue
    print(f"  {name_en} / {name_ar}")
    img = try_ar_wiki(name_ar, name_en, name_ar)
    if img:
        result = save_img(eid, img)
        if result != "ok": print(f"    ✗ {result}")
    else:
        print(f"    ✗ not found")
    time.sleep(1.5)

print("\nDone. Check what's downloaded and commit:")
print("  git add emblems/")
print("  git commit -m 'Add more Palestinian emblems'")
print("  git push")
