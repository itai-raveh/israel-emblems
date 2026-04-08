#!/usr/bin/env python3
"""
scraper_missing.py — Targeted scraper for missing municipalities.
Fetches actual Hebrew Wikipedia HTML to get resource= attribute.
Saves to output_missing/ for review before committing to repo.

Run:
    python3 scraper_missing.py --repo ~/Documents/GitHub/israel-emblems --csv ~/Documents/GitHub/israel-emblems/data/municipalities.csv
    python3 scraper_missing.py --repo ~/Documents/GitHub/israel-emblems --csv ~/Documents/GitHub/israel-emblems/data/municipalities.csv --go
"""

import re, time, urllib.parse, argparse
from pathlib import Path

import requests, pandas as pd
from bs4 import BeautifulSoup

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "IsraelMunicipalEmblemsBot/8.0 (research; mailto:your@email.com)"})

HE_WIKI = "https://he.wikipedia.org/wiki/"
EN_WIKI = "https://en.wikipedia.org/wiki/"
HE_API  = "https://he.wikipedia.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
DELAY   = 1.5
TIMEOUT = 20

# Hebrew Wikipedia title overrides — spaces not hyphens
HE_TITLES = {
    "binyamina":      "בנימינה-גבעת עדה",
    "gan-yavne":      "גן יבנה",
    "pardes-hanna":   "פרדס חנה-כרכור",
    "bnei-shimon":    "בני שמעון",
    "golan":          "מועצה אזורית גולן",
    "mateh-asher":    "מטה אשר",
    "misgav":         "מסגב",
    "shafir":         "שפיר",
    "kiryat-tivon":   "קריית טבעון",
    "rosh-pina":      "ראש פינה",
    "ramat-negev":    "רמת נגב",
    "abu-ghosh":      "אבו גוש",
    "beit-el":        "בית אל",
    "buqata":         "בוקעאתה",
    "elkana":         "אלקנה",
    "elyakhin":       "אליכין",
    "har-adar":       "הר אדר",
    "ibillin":        "אעבלין",
    "jaljulye":       "ג'לג'וליה",
    "kedumim":        "קדומים",
    "kfar-yona":      "כפר יונה",
    "migdal":         "מגדל",
    "nein":           "ניין",
    "taibeh-north":   "טייבה",
    "lehavim":        "להבים",
    "maale-iron":     "מעלה עירון",
    "migdal-tefen":   "מגדל תפן",
    "oranit":         "אורנית",
    "rekhasim":       "רכסים",
    "shlomi":         "שלומי",
    "beer-tuvia":     "באר טוביה",
    "emek-hamayanot": "עמק המעיינות",
    "gan-rave":       "גן רווה",
    "har-hevron":     "הר חברון",
    "hevel-eilot":    "חבל אילות",
    "hof-ashkelon":   "חוף אשקלון",
    "jordan-valley":  "בקעת הירדן",
    "lev-hasharon":   "לב השרון",
    "maale-yosef":    "מעלה יוסף",
    "mateh-yehuda":   "מטה יהודה",
    "merom-hagalil":  "מרום הגליל",
    "mevoot-hermon":  "מבואות חרמון",
    "sdot-negev":     "שדות נגב",
    # from annotations - these were marked missing but scraper should retry
    "rehovot":        "רחובות",
    "kfar-saba":      "כפר סבא",
    "modiin":         "מודיעין-מכבים-רעות",
    "nazareth":       "נצרת",
    "ramla":          "רמלה",
    "raanana":        "רעננה",
    "nahariya":       "נהריה",
    "nes-ziona":      "נס ציונה",
    "elad":           "אלעד",
    "karmiel":        "כרמיאל",
    "netivot":        "נתיבות",
    "ofakim":         "אופקים",
    "rahat":          "רהט",
    "sderot":         "שדרות",
    "tzfat":          "צפת",
    "umm-al-fahm":    "אום אל-פחם",
    "yavne":          "יבנה",
    "rosh-haayin":    "ראש העין",
    "beitar-illit":   "ביתר עילית",
    "hod-hasharon":   "הוד השרון",
    "harish":         "חריש",
    "migdal-haemek":  "מגדל העמק",
    "nesher":         "נשר",
    "tirat-carmel":   "טירת כרמל",
    "yeroham":        "ירוחם",
    "megiddo":        "מגידו",
    "shomron":        "שומרון",
    "jerusalem":      "ירושלים",
    "holon":          "חולון",
}

UI_ICONS = re.compile(
    r"Wikidata.logo|Disambig|Wiktionary.logo|Wikispecies|Crystal_Clear|"
    r"Incomplete.document|No_free_image|Europe_w_asia|help_index|WikiAir",
    re.IGNORECASE
)

def safe_part(s):
    return re.sub(r'[\\/*?:"<>|]', "_", str(s or "")).strip("_ ")

def fetch_html(title):
    url = HE_WIKI + urllib.parse.quote(title.replace(" ", "_"), safe="/:,'-().")
    try:
        r = SESSION.get(url, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200: return r.text
    except Exception as e:
        print(f"    ⚠ {e}")
    return None

def extract_resource(html):
    soup = BeautifulSoup(html, "html.parser")
    infobox = (
        soup.find("table", class_=re.compile(r"infobox", re.I)) or
        soup.find("table", class_=re.compile(r"wikitable", re.I)) or
        soup.find("table")
    )
    if not infobox: return None, None
    for img in infobox.find_all("img"):
        resource = img.get("resource", "")
        src = img.get("src", "")
        width = int(img.get("width", 0) or 0)
        if 0 < width < 20: continue
        if resource:
            m = re.search(r"wiki/(?:קובץ|File|Image):(.+)$", resource, re.IGNORECASE)
            if m:
                filename = urllib.parse.unquote(m.group(1)).strip()
                if filename and not UI_ICONS.search(filename):
                    if src.startswith("//"): src = "https:" + src
                    return filename, src
    return None, None

def get_file_url(api_url, prefix, filename):
    filename = filename.replace(" ", "_")
    if filename: filename = filename[0].upper() + filename[1:]
    try:
        r = SESSION.get(api_url, params={
            "action":"query","titles":f"{prefix}:{filename}",
            "prop":"imageinfo","iiprop":"url|mime","format":"json"
        }, timeout=TIMEOUT)
        if not r.text.strip(): return None
        pages = r.json().get("query",{}).get("pages",{})
        for page in pages.values():
            if page.get("pageid",-1)==-1: return None
            return page.get("imageinfo",[{}])[0].get("url")
    except: return None

def resolve_url(filename, src):
    is_svg = filename.lower().endswith(".svg")
    if "wikipedia/he" in src:
        url = get_file_url(HE_API, "קובץ", filename) or get_file_url(COMMONS, "File", filename)
    else:
        url = get_file_url(COMMONS, "File", filename) or get_file_url(HE_API, "קובץ", filename)
    return url, is_svg

def thumbnail_url(url, width=800):
    m = re.match(r"(https://upload\.wikimedia\.org/wikipedia/(?:commons|he)/)([a-f0-9]/[a-f0-9]{2}/)(.+)", url)
    if m: return f"{m.group(1)}thumb/{m.group(2)}{m.group(3)}/{width}px-{m.group(3)}.png"
    return url

def download(url, dest):
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"    ⚠ download: {e}")
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--csv',  required=True)
    parser.add_argument('--go',   action='store_true')
    args = parser.parse_args()

    repo     = Path(args.repo)
    out_dir  = repo / 'output_missing'
    out_dir.mkdir(exist_ok=True)

    df = pd.read_csv(args.csv, dtype=str).fillna('')
    # Get all missing rows that have a HE_TITLES entry
    targets = df[df['status']=='not-found'].copy()

    mode = "DOWNLOADING" if args.go else "DRY RUN"
    print(f"\n{'='*65}\nscraper_missing.py — {mode} — {len(targets)} targets\n{'='*65}\n")

    found, not_found = [], []

    for _, row in targets.iterrows():
        muni_id  = row['id']
        name_he  = row['name_he']
        name_en  = row['name_en']
        wiki_title = HE_TITLES.get(muni_id, name_he.replace("-", " "))

        print(f"\n[{muni_id}] {name_en}")

        time.sleep(DELAY)
        html = fetch_html(wiki_title)
        if not html:
            print(f"  ✗ page not found: {wiki_title!r}")
            not_found.append(muni_id)
            continue

        print(f"  → page: {wiki_title!r}")
        filename, src = extract_resource(html)

        if not filename:
            print(f"  ✗ no emblem in infobox")
            not_found.append(muni_id)
            continue

        print(f"  ✓ {filename!r}")

        time.sleep(DELAY)
        url, is_svg = resolve_url(filename, src or "")
        if not url:
            print(f"  ✗ URL failed")
            not_found.append(muni_id)
            continue

        ext  = "svg" if is_svg else "png"
        base = re.sub(r"\.(svg|png|jpg|jpeg|gif|webp)$", "", filename, flags=re.IGNORECASE)
        new_name = (f"{safe_part(muni_id)}__{safe_part(name_he)}__{safe_part(row['type'])}__"
                    f"{safe_part(row['district'])}__{safe_part(row['culture'])}__{safe_part(base)}.{ext}")

        found.append((muni_id, new_name))
        dest = out_dir / new_name

        if args.go:
            time.sleep(DELAY)
            if download(url, dest):
                print(f"  📥 {ext.upper()} → {new_name}")
                if is_svg:
                    thumb = out_dir / f"{dest.stem}.png"
                    download(thumbnail_url(url), thumb)
            else:
                not_found.append(muni_id)
        else:
            print(f"  → would save: {new_name}")

    print(f"\n{'='*65}")
    print(f"Found: {len(found)}  |  Not found: {len(not_found)}")
    if not_found:
        print(f"\nStill missing:")
        for m in not_found: print(f"  • {m}")
    print(f"{'='*65}\n")

    if args.go:
        print(f"Files saved to: {out_dir}/")
        print(f"Review, then use import_manual.py to bring into repo.")
    else:
        print(f"Add --go to download:")
        print(f"  python3 scraper_missing.py --repo {args.repo} --csv {args.csv} --go\n")

if __name__ == '__main__':
    main()
