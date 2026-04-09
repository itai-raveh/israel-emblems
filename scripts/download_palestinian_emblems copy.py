#!/usr/bin/env python3
import csv, os, re, time, urllib.parse
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "emblems-research-bot/1.0 (github.com/itai-raveh/israel-emblems)"})

SVG_DIR = "emblems/svg"
PNG_DIR = "emblems/png"
os.makedirs(SVG_DIR, exist_ok=True)
os.makedirs(PNG_DIR, exist_ok=True)

BAD_WORDS  = ["flag","map","location","locator","skyline","panorama","mosque","church",
              "street","road","aerial","satellite","flag of palestine","flag of the","governorate"]
GOOD_WORDS = ["seal","coat","coa","emblem","logo","شعار","خاتم","ختم",
              "municipal","municipality","city logo","official logo","official seal","badge"]

def score_img(img, name_en, name_ar):
    src = img.get("src","")
    alt = img.get("alt","").lower()
    combined = (src+" "+alt).lower()
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
        if s >= 0: candidates.append((s, img))
    if not candidates: return None
    candidates.sort(reverse=True)
    best_score, best_img = candidates[0]
    return best_img if best_score >= 1 else None

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
        if ext in ("tif","tiff"):
            return src, filename.rsplit(".",1)[0]+".png"
        return f"https://{base}/{hashpath}", filename
    filename = unquote(src.rsplit("/",1)[-1].split("?")[0])
    return src, filename

def get_soup(url):
    r = SESSION.get(url, timeout=15)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def try_wiki(lang, title, name_en, name_ar):
    slug = urllib.parse.quote(title.replace(" ","_"), safe="")
    url  = f"https://{lang}.wikipedia.org/wiki/{slug}"
    try:
        soup = get_soup(url)
        return extract_infobox_image(soup, name_en, name_ar)
    except Exception as e:
        print(f"      [{lang}] error: {e}")
        return None

def download(url, dest):
    r = SESSION.get(url, timeout=30, stream=True)
    r.raise_for_status()
    with open(dest,"wb") as f:
        for chunk in r.iter_content(8192): f.write(chunk)
    return os.path.getsize(dest)

def process(eid, name_en, name_ar, name_he):
    svg_path = os.path.join(SVG_DIR, f"{eid}-COA.svg")
    png_path = os.path.join(PNG_DIR, f"{eid}-COA.png")
    if os.path.exists(svg_path): return {"status":"skip-svg","file":svg_path}
    if os.path.exists(png_path): return {"status":"skip-png","file":png_path}

    img, lang = None, None
    img = try_wiki("en", name_en, name_en, name_ar)
    if img: lang = "en"
    time.sleep(0.5)
    if not img and name_ar:
        img = try_wiki("ar", name_ar, name_en, name_ar)
        if img: lang = "ar"
        time.sleep(0.5)
    if not img: return {"status":"not-found"}

    try:
        orig_url, filename = resolve_original_url(img)
    except Exception as e:
        return {"status":"url-error","error":str(e)}

    ext = filename.rsplit(".",1)[-1].lower() if "." in filename else "png"
    if ext == "svg":   dest, ftype = svg_path, "svg"
    elif ext == "gif": dest, ftype = os.path.join(PNG_DIR,f"{eid}-COA.gif"), "gif"
    else:              dest, ftype = png_path, "png"

    try:
        size = download(orig_url, dest)
        return {"status":f"ok-{ftype}","file":dest,"source_wiki":lang,
                "source_file":filename,"size_kb":size//1024}
    except Exception as e:
        return {"status":"download-error","error":str(e),"url":orig_url}

def main():
    csv_path = "data/palestinian_municipalities.csv"
    if not os.path.exists(csv_path):
        print(f"ERROR: {csv_path} not found - run from repo root."); return

    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    print(f"Processing {len(rows)} entities\n")
    report = []
    counts = dict(svg=0,png=0,skip=0,missing=0,error=0)
    ICONS  = {"ok-svg":"✅","ok-png":"🖼","ok-gif":"🖼","skip-svg":"⏭","skip-png":"⏭",
              "not-found":"✗","url-error":"⚠","download-error":"💥"}

    for i, row in enumerate(rows,1):
        eid      = row["id"]
        name_en  = row["name_en"]
        name_ar  = row.get("name_ar","")
        name_he  = row.get("name_he","")
        district = row.get("district","")
        print(f"[{i:3}/{len(rows)}] {name_en:40} ({district})")

        res    = process(eid, name_en, name_ar, name_he)
        status = res.get("status","error")
        icon   = ICONS.get(status,"?")

        if status.startswith("ok"):
            ftype = status.split("-")[1]
            print(f"      {icon} {ftype.upper()} from [{res['source_wiki']}] "
                  f"({res.get('size_kb','?')}KB) <- {res.get('source_file','')[:55]}")
            counts["svg" if ftype=="svg" else "png"] += 1
        elif status.startswith("skip"):
            print(f"      {icon} Already downloaded")
            counts["skip"] += 1
        elif status == "not-found":
            print(f"      {icon} Not found on Wikipedia")
            counts["missing"] += 1
        else:
            print(f"      {icon} {status}: {res.get('error','')[:60]}")
            counts["error"] += 1

        report.append({"id":eid,"name_en":name_en,**res})
        time.sleep(0.4)

    fields = ["id","name_en","status","file","source_wiki","source_file","size_kb","error","url"]
    with open("download_report.csv","w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in report: w.writerow({k:r.get(k,"") for k in fields})

    total = counts["svg"]+counts["png"]
    print(f"\n{'='*50}")
    print(f"SVG downloaded : {counts['svg']}")
    print(f"PNG downloaded : {counts['png']}")
    print(f"Already had    : {counts['skip']}")
    print(f"Not found      : {counts['missing']}")
    print(f"Errors         : {counts['error']}")
    print(f"\nReport -> download_report.csv")
    print(f"\nNext:")
    print(f"  git add emblems/")
    print(f"  git commit -m \"Add Palestinian municipal emblems ({total} files)\"")
    print(f"  git push")

if __name__ == "__main__":
    main()
