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
    "rtf nach gps": "rtf",
    "rtf": "rtf",
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

geocode_cache = {}

def geocode(query):
    if not query or len(query) < 2:
        return None
    key = query.strip().lower()
    if key in geocode_cache:
        return geocode_cache[key]
    try:
        resp = requests.get(NOMINATIM_URL, params={
            "q": query,
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
        time.sleep(1.1)  # Nominatim fair-use: max 1 req/sec
        return result
    except Exception as e:
        print(f"    Geocoding fehler: {e}")
        return None

def is_datum(text):
    return bool(re.match(r'^(Mo|Di|Mi|Do|Fr|Sa|So),\s+\d{2}\.\d{2}\.\d{4}$', text))

def is_km(text):
    return bool(re.match(r'^\d[\d/]*$', text))

def is_typ(text):
    return text.lower().strip() in TYPE_KEYWORDS

def parse_typ(text):
    return TYPE_KEYWORDS.get(text.lower().strip(), "rtf")

def scrape_detail(url):
    """
    Ruft die Detailseite auf und extrahiert:
    - Startort (PLZ + Ort)
    - Startzeit
    - Webseite des Vereins
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        result = {
            "startort": "",
            "startort_adresse": "",
            "startzeit": "",
            "webseite": "",
            "landesverband": "",
        }

        # Tabelle mit Details parsen
        rows = soup.select("table tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(separator=" ", strip=True)

            if "startort" in label:
                # Startort enthält oft: "Straße PLZ Ort Zusatz"
                result["startort_adresse"] = value
                # PLZ + Ort extrahieren: suche nach 5-stelliger PLZ
                m = re.search(r'(\d{5})\s+([A-ZÄÖÜa-zäöü][^\n\r]+?)(?:\s+[A-Z][a-z]|\s*$)', value)
                if m:
                    result["startort"] = m.group(1) + " " + m.group(2).strip()
                else:
                    # Fallback: letzter sinnvoller Teil
                    result["startort"] = value.split("Route")[0].strip()

            elif "startzeit" in label:
                result["startzeit"] = value

            elif "internet" in label:
                link = cells[1].find("a")
                if link:
                    result["webseite"] = link.get("href", "")

            elif "landesverband" in label:
                result["landesverband"] = value

        return result

    except Exception as e:
        print(f"    Fehler beim Laden der Detailseite: {e}")
        return {"startort": "", "startort_adresse": "", "startzeit": "", "webseite": "", "landesverband": ""}

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
            elif not titel and not is_datum(line) and not is_km(line) and not is_typ(line) and len(line) > 2:
                titel = line

        if not titel:
            for line in lines:
                if not is_datum(line) and not is_km(line) and not is_typ(line):
                    titel = line
                    break

        verein_clean = re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', verein_raw).strip()

        if not datum and not titel:
            continue

        events.append({
            "titel": titel,
            "datum": datum,
            "typ": typ,
            "km": km,
            "verein": verein_clean,
            "startort": "",
            "startort_adresse": "",
            "startzeit": "",
            "webseite": "",
            "landesverband": "",
            "url": full_url,
            "lat": None,
            "lng": None
        })

    return events

def main():
    print("=" * 55)
    print("Radsport Breitensportkalender Scraper")
    print("=" * 55)

    # Schritt 1: Alle Termine von der Übersicht laden
    print("\nSchritt 1: Lade alle Termine...")
    all_events = []

    for start in range(0, 750, 30):
        print(f"  Seite {start//30 + 1}: Eintraege {start+1}-{start+30}...")
        events = scrape_page(start)
        if not events:
            print("  Keine weiteren Eintraege, fertig.")
            break
        all_events.extend(events)
        time.sleep(2)

    # Duplikate entfernen
    seen = set()
    unique = []
    for e in all_events:
        if e["url"] not in seen:
            seen.add(e["url"])
            unique.append(e)
    all_events = unique
    print(f"\n{len(all_events)} eindeutige Termine gefunden.")

    # Schritt 2: Detailseiten abrufen
    print("\nSchritt 2: Lade Detailseiten fuer genaue Startorte...")
    for i, event in enumerate(all_events):
        print(f"  [{i+1}/{len(all_events)}] {event['titel'][:40]}...")
        details = scrape_detail(event["url"])
        event["startort"] = details["startort"]
        event["startort_adresse"] = details["startort_adresse"]
        event["startzeit"] = details["startzeit"]
        event["webseite"] = details["webseite"]
        event["landesverband"] = details["landesverband"]
        time.sleep(1.5)  # Hoefliche Pause

    # Schritt 3: Geocoding
    print("\nSchritt 3: Geocoding der Startorte...")
    for i, event in enumerate(all_events):
        ort = event.get("startort", "")
        if not ort:
            continue
        print(f"  [{i+1}/{len(all_events)}] {ort}")
        coords = geocode(ort + ", Deutschland")
        if coords:
            event["lat"] = coords["lat"]
            event["lng"] = coords["lng"]
        else:
            print(f"    -> Nicht gefunden")

    # Speichern
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    geocoded = sum(1 for e in all_events if e["lat"])
    print(f"\n{'='*55}")
    print(f"Fertig!")
    print(f"  {len(all_events)} Termine gespeichert")
    print(f"  {geocoded} mit GPS-Koordinaten ({geocoded*100//len(all_events) if all_events else 0}%)")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
