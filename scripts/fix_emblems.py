#!/usr/bin/env python3
"""
fix_emblems.py — Round 2 cleanup and retry
===========================================
1. Deletes all Red_pog.svg false positives
2. Deletes 4 known wrong images
3. Retries rate-limited + not-found via Arabic Wikipedia
4. Tries direct known Commons filenames for major cities

Run from repo root:
    python3 fix_emblems.py
"""

import csv, os, re, time, urllib.parse
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "emblems-research-bot/1.0 (github.com/itai-raveh/israel-emblems)"})

SVG_DIR = "emblems/svg"
PNG_DIR = "emblems/png"

# ── Step 1: Delete Red_pog false positives and wrong images ───────────────────

RED_POG_IDS = [
    "ps-wb-halhul","ps-wb-battir","ps-wb-beit-fajjar","ps-wb-nahhalin","ps-wb-tuqu",
    "ps-wb-beit-ummar","ps-wb-sair","ps-wb-surif","ps-wb-tarqumiyah","ps-wb-kafr-dan",
    "ps-wb-kafr-rai","ps-wb-yabad","ps-wb-abu-dis","ps-wb-beit-furik","ps-wb-beit-iba",
    "ps-wb-huwwara","ps-wb-azzun","ps-wb-habla","ps-wb-jayyus","ps-wb-kafr-qaddum",
    "ps-wb-beitin","ps-wb-bir-zeit","ps-wb-budrus","ps-wb-nilin","ps-wb-sinjil",
    "ps-wb-bidya","ps-wb-deir-ballut","ps-wb-qarawat-bani-hassan","ps-wb-tammun",
    "ps-wb-anabta","ps-wb-baqa-ash-sharqiyya","ps-gz-jabalia","ps-gz-zawaida",
    "ps-gz-al-bureij","ps-gz-abasan-al-kabira","ps-gz-al-fukhari","ps-gz-al-qarara",
]

WRONG_IMAGE_IDS = [
    "ps-wb-jericho-governorate",      # landscape photo
    "ps-wb-qalqilya-governorate",     # cemetery photo
    "ps-wb-tulkarm-governorate",      # cemetery photo
    "ps-wb-marda",                    # aerial crop
    "ps-wb-ramallah-and-al-bireh-governorate",  # city skyline (if it downloaded)
]

def delete_file(eid):
    for folder, ext in [(SVG_DIR,"svg"),(PNG_DIR,"png"),(PNG_DIR,"gif")]:
        path = os.path.join(folder, f"{eid}-COA.{ext}")
        if os.path.exists(path):
            os.remove(path)
            print(f"  🗑  Deleted {path}")

print("Step 1: Cleaning up false positives...")
for eid in RED_POG_IDS + WRONG_IMAGE_IDS:
    delete_file(eid)

# ── Helpers ───────────────────────────────────────────────────────────────────

BAD_WORDS  = ["flag","map","location","locator","skyline","panorama","mosque","church",
              "street","road","aerial","satellite","flag of","cemetery","cropped",
              "Red_pog","red pog","مساء","مدينة رام"]
GOOD_WORDS = ["seal","coat","coa","emblem","logo","شعار","خاتم","ختم",
              "municipal","municipality","official logo","official seal","badge"]

def score_img(img, name_en, name_ar):
    src = img.get("src","")
    alt = img.get("alt","").lower()
    combined = (src+" "+alt).lower()
    if "Red_pog" in src or "red_pog" in src.lower(): return -99  # hard exclude
    if any(b in combined for b in BAD_WORDS): return -1
    score = sum(5 for g in GOOD_WORDS if g in combined)
    if name_en and name_en.lower() in combined: score += 3
    if name_ar:
        score += sum(2 for p in name_ar.split() if len(p)>2 and p in combined)
    if "/commons/" in src: score += 2
    try:
        if int(img.get("width",999)) < 200: score += 1
    except: pass
    return score

def extract_infobox_image(soup, name_en, name_ar):
    infobox = (soup.find("table", class_=re.compile(r"infobox")) or
               soup.find("table", class_=re.compile(r"vcard")) or
               soup.find("table", class_=re.compile(r"ib-")))
    if not infobox: return None
    candidates = []
    for img in infobox.find_all("img"):
        src = img.get("src","")
        if not src or "1x1" in src: continue
        s = score_img(img, name_en, name_ar)
        if s >= 1: candidates.append((s, img))
    if not candidates: return None
    candidates.sort(reverse=True)
    return candidates[0][1]

def resolve_original_url(img):
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
    filename = unquote(src.rsplit("/",1)[-1].split("?")[0])
    return src, filename

def get_soup(url):
    r = SESSION.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def download(url, dest):
    r = SESSION.get(url, timeout=30, stream=True)
    r.raise_for_status()
    with open(dest,"wb") as f:
        for chunk in r.iter_content(8192): f.write(chunk)
    return os.path.getsize(dest)

def try_wiki(lang, title, name_en, name_ar, delay=1.5):
    slug = urllib.parse.quote(title.replace(" ","_"), safe="")
    url  = f"https://{lang}.wikipedia.org/wiki/{slug}"
    try:
        soup = get_soup(url)
        img  = extract_infobox_image(soup, name_en, name_ar)
        time.sleep(delay)
        return img
    except Exception as e:
        print(f"    [{lang}] error: {e}")
        time.sleep(delay)
        return None

def try_download(eid, img, label=""):
    try:
        orig_url, filename = resolve_original_url(img)
    except Exception as e:
        return f"url-error: {e}"
    ext = filename.rsplit(".",1)[-1].lower() if "." in filename else "png"
    if ext == "svg":   dest = os.path.join(SVG_DIR, f"{eid}-COA.svg")
    elif ext == "gif": dest = os.path.join(PNG_DIR, f"{eid}-COA.gif")
    else:              dest = os.path.join(PNG_DIR, f"{eid}-COA.png")
    try:
        size = download(orig_url, dest)
        print(f"    ✅ {ext.upper()} {label} ({size//1024}KB) ← {filename[:55]}")
        return "ok"
    except Exception as e:
        return f"download-error: {e}"

# ── Step 2: Known direct Commons filenames for major cities ───────────────────
# These were confirmed from your sample HTML snippets + known Wikipedia content

DIRECT_COMMONS = {
    # id: (commons_filename, file_type)
    "ps-wb-hebron":     ("Seal_of_Hebron.tif", "tif"),   # from your sample
    "ps-gz-gaza-city":  ("Gaza_city_coat_of_arms.svg", "svg"),
    "ps-gz-rafah":      ("Rafah_coat_of_arms.svg", "svg"),
}

DIRECT_EN_WIKI = {
    # id: (en_wiki_path, filename)
    "ps-wb-ramallah":   ("Ramallah","Ramallah_Logo.gif"),
    "ps-wb-nablus":     ("Nablus","Nablus_Logo.jpg"),
    "ps-wb-jenin":      ("Jenin","Jenin_Logo.gif"),
    "ps-wb-jericho":    ("Jericho","Jericho_Logo.gif"),
    "ps-wb-salfit":     ("Salfit","Salfitlogo.jpg"),
    "ps-wb-tubas":      ("Tubas","Tubas_Logo.gif"),
    "ps-wb-dura":       ("Dura,_West_Bank","Dura_Logo.gif"),
    "ps-wb-yatta":      ("Yatta","Yatta_Logo.gif"),
}

# ── Step 2a: Direct Commons for Hebron etc ────────────────────────────────────
print("\nStep 2: Trying direct Commons URLs for known major cities...")
COMMONS_BASE = "https://upload.wikimedia.org/wikipedia/commons"

for eid, (filename, ftype) in DIRECT_COMMONS.items():
    svg_path = os.path.join(SVG_DIR, f"{eid}-COA.svg")
    png_path = os.path.join(PNG_DIR, f"{eid}-COA.png")
    if os.path.exists(svg_path) or os.path.exists(png_path):
        print(f"  ⏭  {eid} already downloaded")
        continue
    # Build URL using md5 hash path (Wikipedia convention)
    import hashlib
    h = hashlib.md5(filename.encode()).hexdigest()
    url = f"{COMMONS_BASE}/{h[0]}/{h[0:2]}/{urllib.parse.quote(filename)}"
    dest = svg_path if ftype=="svg" else png_path
    try:
        size = download(url, dest)
        print(f"  ✅ {eid}: {filename} ({size//1024}KB)")
    except Exception as e:
        print(f"  ✗  {eid}: {e}")
    time.sleep(2)

# ── Step 2b: Retry rate-limited good URLs directly ───────────────────────────
print("\nStep 3: Retrying rate-limited files...")
RATE_LIMITED_DIRECT = {
    "ps-gz-beit-hanoun":  "https://upload.wikimedia.org/wikipedia/en/a/a2/BeitHanoun_Logo.gif",
    "ps-gz-beit-lahiya":  "https://upload.wikimedia.org/wikipedia/en/e/e7/BeitLahia_Logo.jpg",
    "ps-wb-salfit":       "https://upload.wikimedia.org/wikipedia/commons/6/6f/Salfitlogo.jpg",
}
for eid, url in RATE_LIMITED_DIRECT.items():
    svg_path = os.path.join(SVG_DIR, f"{eid}-COA.svg")
    png_path = os.path.join(PNG_DIR, f"{eid}-COA.png")
    gif_path = os.path.join(PNG_DIR, f"{eid}-COA.gif")
    if os.path.exists(svg_path) or os.path.exists(png_path) or os.path.exists(gif_path):
        print(f"  ⏭  {eid} already downloaded")
        continue
    ext = url.rsplit(".",1)[-1].lower()
    dest = gif_path if ext=="gif" else png_path
    try:
        size = download(url, dest)
        print(f"  ✅ {eid}: {url.split('/')[-1]} ({size//1024}KB)")
    except Exception as e:
        print(f"  ✗  {eid}: {e}")
    time.sleep(2)

# ── Step 3: Retry not-found via Arabic Wikipedia ──────────────────────────────
print("\nStep 4: Trying Arabic Wikipedia for not-found cities...")

# Load CSV to get Arabic names
csv_path = "data/palestinian_municipalities.csv"
ar_names = {}
for row in csv.DictReader(open(csv_path, encoding="utf-8")):
    ar_names[row["id"]] = (row["name_en"], row.get("name_ar",""))

NOT_FOUND_IDS = [
    "ps-wb-dura","ps-wb-hebron","ps-wb-yatta","ps-wb-jenin","ps-wb-jericho",
    "ps-wb-nablus","ps-wb-ramallah","ps-wb-tubas",
    "ps-wb-bethlehem-governorate","ps-wb-hebron-governorate",
    "ps-wb-jerusalem-governorate","ps-wb-nablus-governorate",
    "ps-wb-salfit-governorate","ps-wb-tubas-governorate","ps-wb-al-ubeidiyya",
    "ps-wb-arroba","ps-wb-aqraba","ps-wb-asira-ash-shamaliyya",
    "ps-wb-beit-dajan","ps-wb-burin","ps-wb-salim","ps-wb-sebastia",
    "ps-wb-beit-ur-al-fauqa","ps-wb-beit-ur-al-tahta",
    "ps-gz-gaza-city","ps-gz-rafah",
    "ps-gz-deir-al-balah-governorate","ps-gz-gaza-governorate",
    "ps-gz-khan-yunis-governorate","ps-gz-north-gaza-governorate","ps-gz-rafah-governorate",
    "ps-gz-al-maghazi","ps-gz-al-nuseirat","ps-gz-abasan-al-jadida","ps-gz-khuzaa",
]

# Also retry the Red_pog ones via Arabic
RETRY_VIA_AR = [eid for eid in RED_POG_IDS]

for eid in NOT_FOUND_IDS + RETRY_VIA_AR:
    svg_path = os.path.join(SVG_DIR, f"{eid}-COA.svg")
    png_path = os.path.join(PNG_DIR, f"{eid}-COA.png")
    gif_path = os.path.join(PNG_DIR, f"{eid}-COA.gif")
    if os.path.exists(svg_path) or os.path.exists(png_path) or os.path.exists(gif_path):
        continue

    name_en, name_ar = ar_names.get(eid, ("",""))
    if not name_ar:
        print(f"  ✗  {eid}: no Arabic name")
        continue

    print(f"  [{eid}] {name_en} / {name_ar}")
    img = try_wiki("ar", name_ar, name_en, name_ar, delay=2.0)
    if img:
        result = try_download(eid, img, f"[ar]")
        if result != "ok":
            print(f"    ✗ {result}")
    else:
        print(f"    ✗ not found on AR wiki")

print("\nDone! Check emblems/ folder and commit:")
print("  git add emblems/")
print("  git commit -m 'Fix Palestinian emblems: remove false positives, add missing'")
print("  git push")
