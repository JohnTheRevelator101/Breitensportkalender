import requests
from bs4 import BeautifulSoup
import json
import time
import re
import random
import os
import logging
from datetime import date, timedelta

# --- KONFIGURATION ---
BASE_URL = "https://breitensport.rad-net.de/breitensportkalender/"
DETAIL_BASE = "https://breitensport.rad-net.de"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
JSON_FILE = "events_final.json"
LOG_FILE = "scraper.log"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "Referer": "https://breitensport.rad-net.de/breitensportkalender/",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# -----------------------------------------------------------------------
# Datum-Logik: Welcher Zeitraum wird heute gescrapt?
# -----------------------------------------------------------------------

def get_date_range():
    today = date.today()
    weekday = today.weekday()  # 0=Montag, 1=Dienstag, ...

    offsets = {
        0: (0,   90),   # Montag
        1: (91,  180),  # Dienstag
        2: (181, 270),  # Mittwoch
        3: (271, 365),  # Donnerstag
    }
    start_offset, end_offset = offsets.get(weekday, (0, 365))

    start = today + timedelta(days=start_offset)
    end   = today + timedelta(days=end_offset)

    return start.strftime("%d.%m.%Y"), end.strftime("%d.%m.%Y")


# -----------------------------------------------------------------------
# Hilfsfunktionen
# -----------------------------------------------------------------------

def load_data():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_plz_ort(text):
    if not text:
        return ""
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    m = re.search(r"(\d{5})\s+([A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß0-9/\-]+)", text)
    if not m:
        return ""
    plz = m.group(1)
    ort = m.group(2).strip()
    ort = re.split(r"\s+(?:Route|Sportpark|Schulzentrum|Halle|Platz|Straße|Str\b)", ort)[0].strip()
    return f"{plz} {ort}" if ort else ""


def geocode(query):
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "de"},
            headers={"User-Agent": "rad-net-scraper/2.0 (private research)"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        time.sleep(1.2)
        if data:
            return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
    except Exception as e:
        logging.warning(f"Geocoding fehlgeschlagen fuer '{query}': {e}")
    return None


# -----------------------------------------------------------------------
# Detail-Scraping
# -----------------------------------------------------------------------

def scrape_detail(url):
    result = {
        "startort": "",
        "startort_adresse": "",
        "startzeit": "",
        "webseite": "",
        "landesverband": "",
    }

    try:
        time.sleep(random.uniform(10.0, 18.0))
        resp = SESSION.get(url, timeout=20)

        if "Bitte warten" in resp.text or "automatisierter Zugriffe" in resp.text:
            logging.warning(f"Rate-limit-Seite bei {url} - warte 5 Minuten")
            time.sleep(300)
            return None

        if resp.status_code == 429:
            logging.warning(f"HTTP 429 bei {url} - warte 5 Minuten")
            time.sleep(300)
            return None

        if resp.status_code != 200:
            logging.error(f"Status {resp.status_code} bei {url}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(separator=" ", strip=True)

            if "startort" in label:
                result["startort_adresse"] = value
                result["startort"] = extract_plz_ort(value)
            elif "startzeit" in label:
                result["startzeit"] = value
            elif "internet" in label:
                link = cells[1].find("a")
                if link:
                    result["webseite"] = link.get("href", "").strip()
            elif "landesverband" in label:
                result["landesverband"] = value

        if not result["startort"]:
            result["startort"] = extract_plz_ort(soup.get_text(separator=" "))

        return result

    except requests.exceptions.Timeout:
        logging.warning(f"Timeout bei {url}")
        return None
    except Exception as e:
        logging.error(f"Fehler bei {url}: {e}")
        return None


# -----------------------------------------------------------------------
# Hauptprogramm
# -----------------------------------------------------------------------

def main():
    startdate, enddate = get_date_range()
    logging.info(f"Scraper v2 gestartet | Zeitraum: {startdate} - {enddate}")

    try:
        SESSION.get(BASE_URL, timeout=10)
        time.sleep(random.uniform(3.0, 6.0))
    except Exception as e:
        logging.warning(f"Startseite nicht erreichbar: {e}")

    all_events = load_data()
    existing_urls = {e["url"] for e in all_events}

    # Phase 1: URLs sammeln
    logging.info(f"Sammle URLs fuer {startdate} - {enddate} ...")
    new_count = 0
    for start in range(0, 1000, 30):
        params = {"startdate": startdate, "enddate": enddate, "lstart": str(start)}
        try:
            resp = SESSION.get(BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logging.error(f"Uebersichtsseite start={start} fehlgeschlagen: {e}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("a", href=re.compile(r"/termine/\d{4}/"))

        if not links:
            break

        for link in links:
            url = DETAIL_BASE + link.get("href")
            if url not in existing_urls:
                existing_urls.add(url)
                all_events.append({
                    "titel": link.get_text(strip=True)[:80],
                    "url": url,
                    "startort": "",
                })
                new_count += 1

        time.sleep(random.uniform(2.0, 4.0))

    logging.info(f"{new_count} neue Events gefunden.")
    save_data(all_events)

    # Phase 2: Details scrapen (nur Events ohne Startort)
    todo = [e for e in all_events if not (e.get("startort") or e.get("startort_adresse"))]
    logging.info(f"Zu verarbeiten: {len(todo)} Events ohne Startort")

    consecutive_errors = 0

    for i, event in enumerate(todo, 1):
        details = scrape_detail(event["url"])

        if details is None:
            consecutive_errors += 1
            logging.warning(f"[{i}/{len(todo)}] Fehler bei '{event['titel'][:40]}' (Fehler in Folge: {consecutive_errors})")
            if consecutive_errors >= 3:
                logging.error("3 Fehler in Folge - pausiere 10 Minuten")
                time.sleep(600)
                consecutive_errors = 0
            continue

        consecutive_errors = 0
        event.update(details)

        if event["startort"] and not event.get("lat"):
            coords = geocode(event["startort"] + ", Deutschland")
            if coords:
                event["lat"] = coords["lat"]
                event["lng"] = coords["lng"]

        save_data(all_events)
        logging.info(f"[{i}/{len(todo)}] OK {event['titel'][:50]} | Startort: '{event['startort']}'")

    mit_startort = sum(1 for e in all_events if e.get("startort"))
    mit_coords   = sum(1 for e in all_events if e.get("lat"))
    logging.info("=== Scraping abgeschlossen ===")
    logging.info(f"Gesamt: {len(all_events)} | Mit Startort: {mit_startort} | Mit Koordinaten: {mit_coords}")


if __name__ == "__main__":
    main()
