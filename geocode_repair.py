import requests
import json
import time
import re

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Radkalender-Hobby/1.0)"
}

DEUTSCHLAND_MITTE = (51.1638, 10.4478)

geocode_cache = {}

def is_center(lat, lng):
    """Prueft ob Koordinate der Deutschlandmitte entspricht (Fallback von Nominatim)"""
    return abs(lat - DEUTSCHLAND_MITTE[0]) < 0.05 and abs(lng - DEUTSCHLAND_MITTE[1]) < 0.05

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
            if is_center(lat, lng):
                result = None
            else:
                result = {"lat": lat, "lng": lng}
        else:
            result = None
        geocode_cache[key] = result
        time.sleep(1.1)
        return result
    except Exception as e:
        print(f"    Fehler: {e}")
        return None

def extract_ort_from_verein(verein):
    """Extrahiert moeglichen Ortsnamen aus Vereinsname"""
    if not verein:
        return []
    
    orte = []
    
    # Landesverband entfernen
    v = re.sub(r'\s*\([A-Z]{2,4}\)\s*$', '', verein).strip()
    # e.V. entfernen
    v = re.sub(r'\be\.?\s*V\.?\b', '', v, flags=re.IGNORECASE).strip()
    v = v.rstrip(',').strip()
    
    # Letztes Wort (oft Ortsname)
    parts = v.split()
    if parts:
        orte.append(parts[-1])
    
    # Letzten zwei Woerter (fuer zusammengesetzte Ortsnamen wie "Bad Homburg")
    if len(parts) >= 2:
        orte.append(f"{parts[-2]} {parts[-1]}")
    
    return orte

def extract_plz_ort(text):
    """Extrahiert PLZ + Ort aus Adresstext"""
    if not text:
        return None
    m = re.search(r'(\d{5})\s+([A-ZÄÖÜa-zäöüß][^\d\n,]+?)(?:\s+Route|\s+Sport|\s+Halle|\s*$)', text)
    if m:
        return f"{m.group(1)} {m.group(2).strip()}"
    m = re.search(r'(\d{5})', text)
    if m:
        return m.group(1)
    return None

def main():
    print("Lade events.json...")
    with open("events.json", "r", encoding="utf-8") as f:
        events = json.load(f)

    # Alle Koordinaten zuruecksetzen die Deutschlandmitte sind
    reset = 0
    for e in events:
        if e.get("lat") and is_center(e["lat"], e.get("lng", 0)):
            e["lat"] = None
            e["lng"] = None
            reset += 1

    missing = [e for e in events if not e.get("lat")]
    print(f"{len(events)} Termine total")
    print(f"{reset} falsche Koordinaten zurueckgesetzt")
    print(f"{len(missing)} benoetigen Geocoding\n")

    fixed = 0
    for i, event in enumerate(events):
        if event.get("lat") and event.get("lng"):
            continue

        # Baue Liste von Suchanfragen
        queries = []

        # 1. Aus startort (PLZ + Ort)
        startort = event.get("startort", "")
        if startort and len(startort) > 3:
            queries.append(startort + ", Deutschland")
            # Nur Ortsname ohne PLZ
            ohne_plz = re.sub(r'^\d{5}\s*', '', startort).strip()
            if ohne_plz:
                queries.append(ohne_plz + ", Deutschland")

        # 2. Aus startort_adresse
        adresse = event.get("startort_adresse", "")
        if adresse:
            plz_ort = extract_plz_ort(adresse)
            if plz_ort:
                queries.append(plz_ort + ", Deutschland")

        # 3. Aus Vereinsname
        verein_orte = extract_ort_from_verein(event.get("verein", ""))
        for o in verein_orte:
            queries.append(o + ", Deutschland")

        # 4. Aus Landesverband (sehr ungenau, aber besser als nichts)
        lv = event.get("landesverband", "")
        if lv and not queries:
            queries.append(lv + ", Deutschland")

        # Deduplizieren
        seen_q = set()
        unique_queries = []
        for q in queries:
            if q.lower() not in seen_q:
                seen_q.add(q.lower())
                unique_queries.append(q)

        coords = None
        for q in unique_queries:
            print(f"  [{i+1}/{len(events)}] '{q}'")
            coords = geocode(q)
            if coords:
                print(f"    ✓ {coords['lat']:.4f}, {coords['lng']:.4f}")
                break
            else:
                print(f"    ✗")

        if coords:
            event["lat"] = coords["lat"]
            event["lng"] = coords["lng"]
            fixed += 1

    # Speichern
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    total_geocoded = sum(1 for e in events if e.get("lat"))
    print(f"\nFertig!")
    print(f"  {fixed} neue Koordinaten ergaenzt")
    print(f"  {total_geocoded}/{len(events)} Termine haben Koordinaten ({total_geocoded*100//len(events)}%)")

if __name__ == "__main__":
    main()
