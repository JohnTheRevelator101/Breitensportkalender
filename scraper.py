import requests
from bs4 import BeautifulSoup
import json
import time
import re

BASE_URL = "https://breitensport.rad-net.de/breitensportkalender/"
DETAIL_BASE = "https://breitensport.rad-net.de"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Radkalender-Hobby/1.0)"
}

TYPE_KEYWORDS = {
    "radtourenfahrt": "rtf",
    "rtf": "rtf",
    "rtf nach gps": "rtf",
    "radmarathon-cup": "marathon",
    "radmarathon": "marathon",
    "country-tourenfahrt": "ctf",
    "ctf-permanente": "ctf",
    "ctf": "ctf",
    "gravelride": "gravel",
    "permanent gravelride": "gravel",
    "volksradfahren": "volk",
    "radwandern": "volk",
    "vrtf": "vrtf",
    "etappenfahrt": "etappe",
    "brevet": "brevet",
    "sonstige": "sonstige",
}

WOCHENTAGE = {"mo", "di", "mi", "do", "fr", "sa", "so"}

geocode_cache = {}

def geocode(ort):
    if not ort or len(ort) < 2:
        return None
    key = ort.strip().lower()
    if key in geocode_cache:
        return geocode_cache[key]
    try:
        resp = requests.get(NOMINATIM_URL, params={
            "q": ort + ", Deutschland",
            "format": "json",
            "limit": 1,
            "countrycodes": "de"
        }, headers=HEADERS, timeout=10)
        data = resp.json()
        if data:
            result = {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
        else:
            result = None
        geocode_cache[key] = result
        time.sleep(1.1)
        return result
    except Exception as e:
        print(f"  Geocoding fehler fuer '{ort}': {e}")
        return None

def is_datum(text):
    return bool(re.match(r'^(Mo|Di|Mi|Do|Fr|Sa|So),\s+\d{2}\.\d{2}\.\d{4}$', text))

def is_km(text):
    return bool(re.match(r'^\d[\d/]*$', text))

def is_typ(text):
    return text.lower().strip() in TYPE_KEYWORDS

def parse_typ(text):
    return TYPE_KEYWORDS.get(text.lower().strip(), "rtf")

def extract_ort(verein_raw):
    """Extrahiert den Ort aus dem Vereinsnamen."""
    # Entferne Landesverband in Klammern am Ende: "(NRW)", "(HES)" etc.
    v = re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', verein_raw).strip()
    # Häufige Muster: "RSV Muster Köln" -> letztes Wort
    # Aber: "e.V." oder "e. V." ist kein Ort
    # Entferne "e.V." und ähnliches
    v = re.sub(r'\be\.?\s*V\.?\b', '', v, flags=re.IGNORECASE).strip()
    v = v.rstrip(',').strip()
    # Letztes Wort nehmen
    parts = v.split()
    if parts:
        return parts[-1]
    return ""

def scrape_page(start):
    params = {
        "startdate": "01.01.2026",
        "enddate": "31.12.2026",
        "art": "-1",
        "lv": "-1",
        "umkreis": "-1",
        "plz": "",
        "updatet": "",
        "lstart": str(start)
    }
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  Fehler beim Laden: {e}")
        return []

    events = []
    all_links = soup.find_all("a", href=re.compile(r"/termine/\d{4}/"))

    for link in all_links:
        href = link.get("href", "")
        full_url = DETAIL_BASE + href if href.startswith("/") else href

        # Text zeilenweise aufteilen
        raw = link.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in raw.split("\n") if l.strip()]

        if not lines:
            continue

        typ = "rtf"
        datum = ""
        titel = ""
        km = ""
        verein_raw = ""

        for line in lines:
            if is_datum(line):
                datum = line
            elif is_km(line):
                km = line
            elif is_typ(line):
                typ = parse_typ(line)
            elif re.search(r'e\.?\s*V\.?', line) or re.search(r'\([A-Z]{2,4}\)', line):
                verein_raw = line
            elif not titel and not is_datum(line) and not is_km(line) and len(line) > 2:
                titel = line

        # Wenn Titel noch leer: nimm erste nicht-Datum, nicht-KM, nicht-Typ Zeile
        if not titel:
            for line in lines:
                if not is_datum(line) and not is_km(line) and not is_typ(line):
                    titel = line
                    break

        # Ort aus Verein extrahieren
        ort = extract_ort(verein_raw) if verein_raw else ""
        verein_clean = re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', verein_raw).strip()

        if not datum and not titel:
            continue

        events.append({
            "titel": titel,
            "datum": datum,
            "typ": typ,
            "km": km,
            "verein": verein_clean,
            "ort": ort,
            "url": full_url,
            "lat": None,
            "lng": None
        })

    return events

def main():
    print("Starte Scraping von rad-net Breitensportkalender 2026...")
    all_events = []

    for start in range(0, 750, 30):
        print(f"  Lade Eintraege {start+1}-{start+30}...")
        events = scrape_page(start)
        if not events:
            print("  Keine Eintraege gefunden, beende.")
            break
        all_events.extend(events)
        print(f"  -> {len(events)} Termine")
        time.sleep(2)

    # Duplikate entfernen (gleiche URL)
    seen = set()
    unique = []
    for e in all_events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)
    all_events = unique
    print(f"\n{len(all_events)} eindeutige Termine. Starte Geocoding...")

    for i, event in enumerate(all_events):
        ort = event.get("ort", "")
        if ort and len(ort) > 2:
            print(f"  [{i+1}/{len(all_events)}] {event['titel'][:30]} -> {ort}")
            coords = geocode(ort)
            if coords:
                event["lat"] = coords["lat"]
                event["lng"] = coords["lng"]

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    geocoded = sum(1 for e in all_events if e["lat"])
    print(f"\nFertig! {len(all_events)} Termine gespeichert, {geocoded} mit Koordinaten.")

if __name__ == "__main__":
    main()
