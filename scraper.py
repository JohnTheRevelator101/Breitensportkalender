import requests
from bs4 import BeautifulSoup
import json
import time

BASE_URL = "https://breitensport.rad-net.de/breitensportkalender/"
DETAIL_BASE = "https://breitensport.rad-net.de"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "Radkalender-Karte/1.0 (hobby project, only linking to rad-net.de)"
}

TYPE_MAP = {
    "RTF": "rtf",
    "Radmarathon": "marathon",
    "CTF": "ctf",
    "Gravelride": "gravel",
    "Volksradfahren": "volk",
    "vRTF": "vrtf",
    "Etappenfahrt": "etappe",
    "Brevet": "brevet",
}

geocode_cache = {}

def geocode(ort):
    if ort in geocode_cache:
        return geocode_cache[ort]
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
        geocode_cache[ort] = result
        time.sleep(1)  # Nominatim fair-use: max 1 request/sec
        return result
    except Exception as e:
        print(f"  Geocoding fehler für '{ort}': {e}")
        return None

def parse_type(text):
    for key, val in TYPE_MAP.items():
        if key.lower() in text.lower():
            return val
    return "sonstige"

def scrape_page(start):
    url = BASE_URL
    params = {
        "startdate": "01.01.2026",
        "enddate": "31.12.2026",
        "art": "-1",
        "lv": "-1",
        "umkreis": "-1",
        "lstart": start
    }
    resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    events = []

    items = soup.select("ul.termine li")
    for item in items:
        try:
            link_tag = item.find("a")
            if not link_tag:
                continue

            href = link_tag.get("href", "")
            full_url = DETAIL_BASE + href if href.startswith("/") else href

            text = link_tag.get_text(separator="|", strip=True)
            parts = [p.strip() for p in text.split("|") if p.strip()]

            if len(parts) < 3:
                continue

            # Art (Typ) steht manchmal als erstes span
            typ_tag = item.find("span", class_=True)
            typ_text = typ_tag.get_text(strip=True) if typ_tag else ""
            typ = parse_type(typ_text) if typ_text else "rtf"

            # Datum
            datum = ""
            km = ""
            titel = ""
            verein = ""

            for i, part in enumerate(parts):
                if any(m in part for m in ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]):
                    datum = part
                elif any(c.isdigit() for c in part) and ("/" in part or part.endswith("km")):
                    km = part
                elif i == len(parts) - 1:
                    verein = part
                elif titel == "" and part != datum and part != km:
                    titel = part

            # Ort aus Verein extrahieren (steht oft nicht direkt da)
            ort = ""
            if "(" in verein and ")" in verein:
                # Landesverband in Klammern entfernen
                verein_clean = verein[:verein.rfind("(")].strip()
            else:
                verein_clean = verein

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
        except Exception as e:
            print(f"  Fehler beim Parsen: {e}")
            continue

    return events

def scrape_detail(event):
    """Holt Ort aus der Detailseite"""
    try:
        resp = requests.get(event["url"], headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Suche nach Ort/PLZ in der Detailseite
        for row in soup.select("table tr, dl dt, .details"):
            text = row.get_text(strip=True)
            if "Ort:" in text or "Startort:" in text or "Veranstaltungsort:" in text:
                td = row.find_next("td") or row.find_next("dd")
                if td:
                    return td.get_text(strip=True)
        # Fallback: Verein als Ort
        return event["verein"]
    except:
        return event["verein"]

def main():
    print("Starte Scraping von rad-net Breitensportkalender...")
    all_events = []

    # Erste Seite laden um Gesamtzahl zu prüfen
    for start in range(0, 720, 30):
        print(f"  Lade Einträge {start+1}–{start+30}...")
        events = scrape_page(start)
        if not events:
            print("  Keine weiteren Einträge, fertig.")
            break
        all_events.extend(events)
        time.sleep(2)  # Höfliche Pause zwischen Requests

    print(f"\n{len(all_events)} Termine gefunden. Starte Geocoding...")

    for i, event in enumerate(all_events):
        if not event["ort"]:
            # Ort aus Detailseite holen
            ort = scrape_detail(event)
            event["ort"] = ort
            time.sleep(1)

        if event["ort"]:
            print(f"  [{i+1}/{len(all_events)}] Geocodiere: {event['ort']}")
            coords = geocode(event["ort"])
            if coords:
                event["lat"] = coords["lat"]
                event["lng"] = coords["lng"]

    # Speichern
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

    print(f"\nFertig! {len(all_events)} Termine in events.json gespeichert.")

if __name__ == "__main__":
    main()
