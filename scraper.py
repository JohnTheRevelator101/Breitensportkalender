import requests
from bs4 import BeautifulSoup
import json
import time
import re
import random
import os

# Konfiguration
JSON_FILE = "events.json"
BASE_URL = "https://breitensport.rad-net.de/breitensportkalender/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def load_existing_data():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def scrape_detail(url):
    """Holt die Details einer Seite mit Fehlerbehandlung."""
    try:
        # Zufällige Pause, um nicht gesperrt zu werden
        time.sleep(random.uniform(1.5, 3.5)) 
        
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Beispiel-Extraktion (muss evtl. an deine genaue HTML-Struktur angepasst werden)
        details = {
            "startort": "",
            "startort_adresse": "",
            "startzeit": "",
            "webseite": ""
        }
        
        # Suche nach dem Startort (oft in Tabellen oder speziellen Klassen)
        # Hier die Logik einfügen, die du bereits in scrape_detail hattest
        # Beispielhaft:
        table = soup.find("table", class_="termine-detail-table")
        if table:
            for row in table.find_all("tr"):
                text = row.get_text().lower()
                if "startort" in text:
                    details["startort"] = row.find_all("td")[-1].get_text(strip=True)
                elif "zeit" in text:
                    details["startzeit"] = row.find_all("td")[-1].get_text(strip=True)

        return details
    except Exception as e:
        print(f"Fehler bei URL {url}: {e}")
        return None

def main():
    # 1. Vorhandene Daten laden
    all_events = load_existing_data()
    print(f"Geladene Events aus Datei: {len(all_events)}")

    # 2. Schritt 1 (Übersicht) hier nur ausführen, wenn all_events leer ist 
    # ODER neue Events hinzufügen (Logik für Schritt 1 bleibt gleich)
    
    # ... (Dein Code für Schritt 1: Übersicht-Scraping) ...

    # 3. Schritt 2: Nur die Events ergänzen, die noch keinen Startort haben
    print("\nStarte Detail-Scraping...")
    for i, event in enumerate(all_events):
        # Wenn Startort schon da ist, überspringen wir das Event
        if event.get("startort"):
            continue
            
        print(f"[{i+1}/{len(all_events)}] Lade Details für: {event['titel']}")
        
        details = scrape_detail(event["url"])
        
        if details:
            event.update(details)
            # SOFORT SPEICHERN: Wenn das Skript jetzt abbricht, ist alles bis hierher sicher!
            save_data(all_events)
            print(f"    -> Gefunden: {details['startort']}")
        else:
            print("    -> Fehler oder keine Daten (Pause...)")
            time.sleep(5) # Längere Pause bei Fehlern

    print("\nFertig! Alle Daten sind in events.json gespeichert.")

if __name__ == "__main__":
    main()
