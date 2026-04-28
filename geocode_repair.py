import requests
import json
import time
import re

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Radkalender-Hobby/1.0)"
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
        result = {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])} if data else None
        geocode_cache[key] = result
        time.sleep(1.1)
        return result
    except Exception as e:
        print(f"    Fehler: {e}")
        return None

def extract_plz_ort(text):
    """Extrahiert PLZ + Ort aus einem Adresstext"""
    if not text:
        return None
    # Suche nach 5-stelliger PLZ gefolgt von Ortsname
    m = re.search(r'(\d{5})\s+([A-ZÄÖÜ][a-zA-ZäöüÄÖÜß\-\s]+?)(?:\s+[A-Z][a-z]|\s*$|Route|Sport|Halle)', text)
    if m:
        return f"{m.group(1)} {m.group(2).strip()}, Deutschland"
    # Nur PLZ
    m = re.search(r'(\d{5})', text)
    if m:
        return f"{m.group(1)}, Deutschland"
    return None

def best_query(event):
    """Wählt die beste Suchanfrage für ein Event"""
    queries = []

    # 1. Startort (sollte PLZ + Ort enthalten)
    startort = event.get("startort", "")
    if startort and len(startort) > 3:
        queries.append(startort + ", Deutschland")

    # 2. PLZ aus Adresse extrahieren
    adresse = event.get("startort_adresse", "")
    if adresse:
        q = extract_plz_ort(adresse)
        if q and q not in queries:
            queries.append(q)

    # 3. Ort aus Verein ableiten (letztes Wort)
    verein = event.get("verein", "")
    if verein:
        v = re.sub(r'\be\.?\s*V\.?\b', '', verein, flags=re.IGNORECASE).strip()
        parts = v.split()
        if parts:
            queries.append(parts[-1] + ", Deutschland")

    return queries

def main():
    print("Lade events.json...")
    with open("events.json", "r", encoding="utf-8") as f:
        events = json.load(f)

    missing = [e for e in events if not e.get("lat") or not e.get("lng")]
    print(f"{len(events)} Termine total, {len(missing)} ohne Koordinaten\n")

    fixed = 0
    for i, event in enumerate(events):
        if event.get("lat") and event.get("lng"):
            continue  # Schon geocodiert

        queries = best_query(event)
        coords = None

        for q in queries:
            print(f"  [{i+1}/{len(events)}] {event['titel'][:35]} -> '{q}'")
            coords = geocode(q)
            if coords:
                print(f"    ✓ {coords['lat']:.4f}, {coords['lng']:.4f}")
                break
            else:
                print(f"    ✗ Nicht gefunden")

        if coords:
            event["lat"] = coords["lat"]
            event["lng"] = coords["lng"]
            fixed += 1

    # Speichern
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    total_geocoded = sum(1 for e in events if e.get("lat"))
    print(f"\nFertig! {fixed} neue Koordinaten ergänzt.")
    print(f"Gesamt: {total_geocoded}/{len(events)} Termine haben jetzt Koordinaten ({total_geocoded*100//len(events)}%)")

if __name__ == "__main__":
    main()
