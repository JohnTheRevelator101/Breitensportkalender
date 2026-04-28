import requests
from bs4 import BeautifulSoup
import json
import time
import re

BASE_URL = "https://breitensport.rad-net.de/breitensportkalender/"
DETAIL_BASE = "https://breitensport.rad-net.de"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Ein realistischerer User-Agent verhindert Blockaden
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://breitensport.rad-net.de/"
}

TYPE_KEYWORDS = {
    "radtourenfahrt": "rtf", "rtf nach gps": "rtf", "rtf": "rtf",
    "radmarathon-cup": "marathon", "radmarathon": "marathon",
    "country-tourenfahrt": "ctf", "ctf-permanente": "ctf", "ctf": "ctf",
    "gravelride": "gravel", "permanent gravelride": "gravel",
    "volksradfahren": "volk", "radwandern": "volk", "vrtf": "vrtf",
    "etappenfahrt": "etappe", "brevet": "brevet", "sonstige": "sonstige",
}

def parse_typ(text):
    text_l = text.lower().strip()
    for kw, val in TYPE_KEYWORDS.items():
        if kw in text_l:
            return val
    return "rtf"

def geocode(query):
    # Nominatim benötigt zwingend einen User-Agent; bei vielen Anfragen 
    # sollte hier eine E-Mail stehen, um Sperren zu vermeiden.
    try:
        resp = requests.get(NOMINATIM_URL, params={
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "de"
        }, headers=HEADERS, timeout=10)
        data = resp.json()
        if data:
            return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
        return None
    except Exception:
        return None

def scrape_detail(url):
    result = {"startort": "", "startort_adresse": "", "startzeit": "", "webseite": ""}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Suche in allen Tabellenzeilen nach den Labels
        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2: continue
            
            label = cells[0].get_text(strip=True).lower()
            # separator=" " hilft, Zeilenumbrüche in Adressen sauber zu trennen
            value = cells[1].get_text(separator=" ", strip=True)

            if "startort" in label or "veranstaltungsort" in label:
                result["startort_adresse"] = value
                # PLZ und Ort extrahieren (5 Ziffern gefolgt von Wort)
                m = re.search(r'(\d{5})\s+([A-Za-zÄÖÜäöüß\-\s]+)', value)
                if m:
                    result["startort"] = f"{m.group(1)} {m.group(2).strip()}"
            elif "startzeit" in label:
                result["startzeit"] = value
            elif "internet" in label:
                a = cells[1].find("a")
                if a: result["webseite"] = a.get("href")
                
    except Exception as e:
        print(f"    Fehler Detailseite: {e}")
    return result

def scrape_page(start):
    params = {
        "startdate": "01.01.2026", "enddate": "31.12.2026",
        "art": "-1", "lv": "-1", "lstart": str(start)
    }
    events = []
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Wir suchen die Tabelle. Rad-net nutzt oft eine Struktur, bei der 
        # die Termine in <tr> Elementen liegen.
        rows = soup.find_all("tr")
        for row in rows:
            # Check, ob ein Link zu einem Termin drin ist
            link = row.find("a", href=re.compile(r"/termine/\d{4}/"))
            if not link: continue
            
            cols = row.find_all("td")
            # In der Regel: [0] Datum, [1] Typ/KM, [2] Titel
            if len(cols) >= 3:
                datum = cols[0].get_text(strip=True)
                typ_raw = cols[1].get_text(strip=True)
                titel = link.get_text(strip=True)
                
                events.append({
                    "titel": titel,
                    "datum": datum,
                    "typ": parse_typ(typ_raw),
                    "km": re.search(r'\d+', typ_raw).group(0) if re.search(r'\d+', typ_raw) else "",
                    "url": DETAIL_BASE + link.get("href") if link.get("href").startswith("/") else link.get("href")
                })
    except Exception as e:
        print(f"  Fehler Seite {start}: {e}")
    return events

def main():
    all_events = []
    print("Starte Scraping...")
    
    # Schritt 1: Übersicht (Paginierung)
    for start in range(0, 150, 30): # Testweise erst mal 5 Seiten
        print(f"Lade Seite ab Eintrag {start}...")
        page_events = scrape_page(start)
        if not page_events: break
        all_events.extend(page_events)
        time.sleep(2) # Höflichkeitspause

    # Schritt 2: Details & Geocoding
    for i, ev in enumerate(all_events):
        print(f"[{i+1}/{len(all_events)}] Details für: {ev['titel'][:30]}...")
        details = scrape_detail(ev["url"])
        ev.update(details)
        
        if ev["startort"]:
            coords = geocode(ev["startort"] + ", Germany")
            if coords:
                ev["lat"], ev["lng"] = coords["lat"], coords["lng"]
        
        time.sleep(1.2) # Wichtig für Nominatim (max 1 req/sec)

    with open("events_2026.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)
    print("Fertig! Datei events_2026.json wurde erstellt.")

if __name__ == "__main__":
    main()
