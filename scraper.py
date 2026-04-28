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
            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])
            # Deutschland-Mittelpunkt filtern (Nominatim Fallback)
            if abs(lat - 51.1638) < 0.01 and abs(lng - 10.4478) < 0.01:
                result = None
            else:
                result = {"lat": lat, "lng": lng}
        else:
            result = None
        geocode_cache[key] = result
        time.sleep(1.1)
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
    """Holt Startort aus der Detailseite - robuste Version"""
    result = {
        "startort": "",
        "startort_adresse": "",
        "startzeit": "",
        "webseite": "",
        "landesverband": "",
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Methode 1: Tabelle mit th/td Paaren
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower().rstrip(":")
            value = cells[1].get_text(separator=" ", strip=True)

            if "startort" in label:
                result["startort_adresse"] = value
    
            # 1. Suche nach 5 Ziffern (PLZ) und dem Wort danach (Ort)
            # Erlaubt auch Bindestriche und Leerzeichen im Ortsnamen
                m = re.search(r'(\d{5})\s+([A-ZÄÖÜa-zäöüß\s\-]+)', value)
            
                if m:
                    plz = m.group(1)
                    ort_raw = m.group(2).strip()
                
                # 2. Den Ort "säubern": Alles abschneiden, was nach dem Ort kommt
                # Wir splitten bei typischen Nachfolgewörtern oder mehreren Leerzeichen
                    ort_clean = re.split(r'\s{2,}|Route|Sport|Halle|Gymnasium|Schule|Anfahrt', ort_raw)[0].strip()
                
                # 3. Ergebnis zusammensetzen
                    result["startort"] = f"{plz} {ort_clean}"
                else:
                # Fallback: Nur die PLZ extrahieren, falls der Rest zu komplex ist
                    m2 = re.search(r'(\d{5})', value)
                    if m2:
                        result["startort"] = m2.group(1)

            elif "startzeit" in label:
                result["startzeit"] = value

            elif "internet" in label:
                link = cells[1].find("a")
                if link:
                    result["webseite"] = link.get("href", "")

            elif "landesverband" in label:
                result["landesverband"] = value

        # Methode 2: Wettervorhersage-Text als Fallback
        if not result["startort"]:
            weather = soup.find(string=re.compile(r"Wettervorhersage für"))
            if weather:
                m = re.search(r'für\s+\*\*(.+?)\*\*', str(weather))
                if not m:
                    m = re.search(r'für\s+(.+?):', str(weather))
                if m:
                    result["startort"] = m.group(1).strip()

        # Methode 3: Google Maps Link als Fallback
        if not result["startort"]:
            maps_link = soup.find("a", href=re.compile(r"maps\.google"))
            if maps_link:
                href = maps_link.get("href", "")
                m = re.search(r'daddr=([^"&]+)', href)
                if m:
                    addr = requests.utils.unquote(m.group(1)).replace("+", " ")
                    result["startort_adresse"] = addr
                    m2 = re.search(r'(\d{5})\s+(\S+)', addr)
                    if m2:
                        result["startort"] = f"{m2.group(1)} {m2.group(2)}"

    except Exception as e:
        print(f"    Fehler: {e}")

    return result

def scrape_page(start):
    params = {
        "startdate": "01.01.2026",
        "enddate": "30.06.2026",
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
    print("Radsport Breitensportkalender Scraper v3")
    print("=" * 55)

    # Schritt 1: Übersicht scrapen
    print("\nSchritt 1: Lade alle Termine...")
    all_events = []

    for start in range(0, 60, 30):
        print(f"  Seite {start//30 + 1}: Eintraege {start+1}-{start+30}...")
        events = scrape_page(start)
        if not events:
            print("  Fertig.")
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
    print(f"\n{len(all_events)} Termine gefunden.")

    # Schritt 2: Detailseiten
    print("\nSchritt 2: Lade Detailseiten...")
    for i, event in enumerate(all_events):
        print(f"  [{i+1}/{len(all_events)}] {event['titel'][:40]}")
        details = scrape_detail(event["url"])
        event.update(details)
        if details["startort"]:
            print(f"    -> {details['startort']}")
        else:
            print(f"    -> kein Startort gefunden")
        time.sleep(1.5)

    # Schritt 3: Geocoding
    print("\nSchritt 3: Geocoding...")
    for i, event in enumerate(all_events):
        ort = event.get("startort", "")
        if not ort:
            continue

        queries = [
            ort + ", Deutschland",
            re.sub(r'^\d{5}\s+', '', ort) + ", Deutschland",  # Nur Ortsname ohne PLZ
        ]

        for q in queries:
            coords = geocode(q)
            if coords:
                event["lat"] = coords["lat"]
                event["lng"] = coords["lng"]
                break

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    geocoded = sum(1 for e in all_events if e.get("lat"))
    print(f"\n{'='*55}")
    print(f"Fertig! {len(all_events)} Termine, {geocoded} mit Koordinaten ({geocoded*100//len(all_events) if all_events else 0}%)")
    print(f"{'='*55}")

if __name__ == "__main__":
    main()
