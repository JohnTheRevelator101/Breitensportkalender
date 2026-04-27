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

TYPE_MAP = {
    "rtf": "rtf",
    "radmarathon": "marathon",
    "radmarathon-cup": "marathon",
    "ctf": "ctf",
    "gravelride": "gravel",
    "volksradfahren": "volk",
    "vrtf": "vrtf",
    "etappenfahrt": "etappe",
    "brevet": "brevet",
    "radwandern": "volk",
}

geocode_cache = {}

def geocode(ort):
    if not ort:
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

def parse_type(text):
    t = text.lower().strip()
    for key, val in TYPE_MAP.items():
        if key in t:
            return val
    return "sonstige"

def extract_ort_from_verein(verein):
    """Versucht den Ort aus dem Vereinsnamen zu extrahieren"""
    # Landesverband in Klammern entfernen: "RSV Muster Köln (NRW)" -> "Köln"
    verein = re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', verein).strip()
    # Letztes Wort oft der Ort
    parts = verein.split()
    if len(parts) >= 2:
        # Versuche letztes Wort als Ort
        return parts[-1]
    return verein

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
        print(f"  Fehler beim Laden von Seite {start}: {e}")
        return []

    events = []

    # Alle li-Elemente mit Links finden
    # Die Struktur ist eine ul ohne Klasse, mit li die Links enthalten
    all_lis = soup.find_all("li")

    for li in all_lis:
        link = li.find("a")
        if not link:
            continue

        href = link.get("href", "")
        # Nur Termine-Links
        if "/termine/" not in href:
            continue

        full_url = DETAIL_BASE + href if href.startswith("/") else href

        # Text des Links aufteilen - durch Zeilenumbrüche getrennt
        raw = link.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in raw.split("\n") if l.strip()]

        if len(lines) < 2:
            continue

        # Typ erkennen (oft erste Zeile, manchmal fehlt er)
        typ = "rtf"
        datum = ""
        titel = ""
        km = ""
        verein = ""

        for i, line in enumerate(lines):
            # Datum erkennen: enthält Wochentag-Kürzel
            if re.search(r'(Mo|Di|Mi|Do|Fr|Sa|So),\s+\d{2}\.\d{2}\.\d{4}', line):
                datum = line
            # KM erkennen: nur Zahlen und Schrägstriche
            elif re.match(r'^[\d/]+$', line) and '/' in line:
                km = line
            # Typ erkennen
            elif any(t in line.lower() for t in TYPE_MAP.keys()):
                typ = parse_type(line)
            # Verein: enthält e.V. oder ähnliches
            elif "e.V." in line or "e. V." in line or "(" in line:
                verein = line
            # Titel: alles andere
            elif titel == "" and datum == "" and len(line) > 3:
                titel = line
            elif titel != "" and datum != "" and verein == "":
                if len(line) > 5 and not re.match(r'^[\d/]+$', line):
                    verein = line

        # Fallback: wenn Titel noch leer
        if not titel and len(lines) >= 2:
            titel = lines[1] if datum else lines[0]

        # Ort aus Verein extrahieren
        ort = extract_ort_from_verein(verein) if verein else ""

        events.append({
            "titel": titel,
            "datum": datum,
            "typ": typ,
            "km": km,
            "verein": re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', verein).strip(),
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
        print(f"  -> {len(events)} Termine gefunden")
        time.sleep(2)

    print(f"\n{len(all_events)} Termine insgesamt. Starte Geocoding...")

    for i, event in enumerate(all_events):
        ort = event.get("ort", "")
        if ort:
            print(f"  [{i+1}/{len(all_events)}] {ort}")
            coords = geocode(ort)
            if coords:
                event["lat"] = coords["lat"]
                event["lng"] = coords["lng"]
            else:
                print(f"    -> Nicht gefunden")

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    geocoded = sum(1 for e in all_events if e["lat"])
    print(f"\nFertig! {len(all_events)} Termine gespeichert, {geocoded} geocodiert.")

if __name__ == "__main__":
    main()
