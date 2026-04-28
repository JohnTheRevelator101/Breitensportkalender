import requests
from bs4 import BeautifulSoup
import json
import time
import re

BASE_URL = "https://breitensport.rad-net.de/breitensportkalender/"
DETAIL_BASE = "https://breitensport.rad-net.de"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "Radkalender-Karte/1.0 (hobby project, contact: gerasch.alexander@gmail.com)"
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
    if not ort or ort in ["", "Unbekannter Ort"]:
        return None
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
        time.sleep(1.2)  # Nominatim Fair-Use
        return result
    except Exception as e:
        print(f"  Geocoding Fehler für '{ort}': {e}")
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
        "lstart": start
    }
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        events = []

        # Sucht Links, die auf ein Termin-Detail verweisen
        links = soup.find_all("a", href=re.compile(r"/termine/2026/"))
        
        for link in links:
            href = link.get("href", "")
            full_url = DETAIL_BASE + href if href.startswith("/") else href
            
            container = link.find_parent(["tr", "li"])
            if not container: continue

            titel = link.get_text(strip=True)
            row_text = container.get_text(" ", strip=True)
            
            # Datum finden
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', row_text)
            datum = date_match.group(1) if date_match else ""

            # Typ finden
            typ = parse_type(row_text)
            
            # KM-Angaben finden (z.B. "150/110/70 km")
            km_match = re.search(r'(\d+[/| \d+]*\s*km)', row_text)
            km = km_match.group(1) if km_match else ""

            events.append({
                "titel": titel,
                "datum": datum,
                "typ": typ,
                "km": km,
                "url": full_url,
                "lat": None,
                "lng": None,
                "ort": "",
                "plz": ""
            })
        return events
    except Exception as e:
        print(f" Fehler beim Laden der Seite {start}: {e}")
        return []

def scrape_detail(event):
    """Extrahiert PLZ und Ort aus der Detailseite"""
    try:
        resp = requests.get(event["url"], headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Methode: Suche nach PLZ und Ort im gesamten Text
        content = soup.get_text(" ", strip=True)
        
        # Regex für 5-stellige PLZ und darauffolgenden Stadtnamen
        match = re.search(r'(\d{5})\s+([A-ZÄÖÜ][a-zäöüß\s\-]+)', content)
        if match:
            plz = match.group(1)
            # Bereinigt den Ort (entfernt "Route berechnen" etc.)
            ort_raw = match.group(2).strip()
            ort_clean = re.split(r'\s{2,}|Route|Anfahrt|Start', ort_raw)[0].strip()
            
            event["plz"] = plz
            event["ort"] = ort_clean
            return f"{plz} {ort_clean}"
        
        return ""
    except:
        return ""

def main():
    print("Starte Scraping für 2026...")
    all_events = []

    # Seiten durchlaufen
    for start in range(0, 600, 30):
        print(f"  Lade Einträge ab {start}...")
        events = scrape_page(start)
        if not events:
            break
        all_events.extend(events)
        time.sleep(1.5)

    if not all_events:
        print("Keine Termine gefunden. Möglicherweise sind für
