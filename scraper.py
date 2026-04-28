import requests
from bs4 import BeautifulSoup
import json
import time
import re
import random
import os
import logging

# --- KONFIGURATION ---
BASE_URL = "https://breitensport.rad-net.de/breitensportkalender/"
DETAIL_BASE = "https://breitensport.rad-net.de"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
JSON_FILE = "events_final.json"
LOG_FILE = "scraper.log"

# Echter Browser-Header gegen Blockaden
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

TYPE_KEYWORDS = {
    "radtourenfahrt": "rtf", "rtf nach gps": "rtf", "rtf": "rtf",
    "radmarathon-cup": "marathon", "radmarathon": "marathon",
    "country-tourenfahrt": "ctf", "ctf-permanente": "ctf", "ctf": "ctf",
    "gravelride": "gravel", "permanent gravelride": "gravel",
    "volksradfahren": "volk", "radwandern": "volk", "vrtf": "vrtf",
    "etappenfahrt": "etappe", "brevet": "brevet", "sonstige": "sonstige"
}

def load_data():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def geocode(query):
    try:
        resp = requests.get(NOMINATIM_URL, params={"q": query, "format": "json", "limit": 1, "countrycodes": "de"}, headers=HEADERS, timeout=10)
        data = resp.json()
        if data:
            return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
        time.sleep(1.2) # Nominatim Limit
    except:
        return None
    return None

def scrape_detail(url):
    result = {"startort": "", "startort_adresse": "", "startzeit": "", "webseite": "", "landesverband": ""}
    try:
        time.sleep(random.uniform(2.5, 4.5)) # Zufällige Pause gegen Bot-Erkennung
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logging.error(f"Status {resp.status_code} bei {url}")
            return None
        
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2: continue
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(separator=" ", strip=True)

            if "startort" in label:
                result["startort_adresse"] = value
                m = re.search(r'(\d{5})\s+([A-ZÄÖÜa-zäöüß\s\-]+)', value)
                if m:
                    result["startort"] = f"{m.group(1)} {m.group(2).strip()}"
            elif "startzeit" in label: result["startzeit"] = value
            elif "internet" in label:
                link = cells[1].find("a")
                if link: result["webseite"] = link.get("href", "")
            elif "landesverband" in label: result["landesverband"] = value
        
        return result
    except Exception as e:
        logging.error(f"Fehler bei {url}: {e}")
        return None

def main():
    logging.info("Scraper gestartet")
    all_events = load_data()
    processed_urls = {e["url"] for e in all_events if e.get("startort")}

    # Schritt 1: URLs sammeln (falls Liste leer)
    if not all_events:
        logging.info("Sammle URLs von Übersichtsseiten...")
        for start in range(0, 300, 30): # Testweise erste 10 Seiten
            params = {"startdate": "01.01.2026", "enddate": "31.12.2026", "lstart": str(start)}
            resp = requests.get(BASE_URL, params=params, headers=HEADERS)
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a", href=re.compile(r"/termine/\d{4}/"))
            for link in links:
                url = DETAIL_BASE + link.get("href")
                if url not in [e["url"] for e in all_events]:
                    all_events.append({"titel": link.get_text(strip=True)[:50], "url": url, "startort": ""})
        save_data(all_events)

    # Schritt 2: Details & Geocoding kombiniert mit "Checkpoint"-Speicherung
    logging.info(f"Verarbeite {len(all_events)} Events...")
    for event in all_events:
        if event["url"] in processed_urls:
            continue

        details = scrape_detail(event["url"])
        if details:
            event.update(details)
            # Direkt Geocoding versuchen
            if event["startort"]:
                coords = geocode(event["startort"] + ", Deutschland")
                if coords:
                    event["lat"], event["lng"] = coords["lat"], coords["lng"]
            
            save_data(all_events) # Speichert nach JEDEM Event
            logging.info(f"Gespeichert: {event['titel']}")
        else:
            logging.warning(f"Pause wegen Fehler bei {event['url']}")
            time.sleep(10)

    logging.info("Scraping beendet.")

if __name__ == "__main__":
    main()
