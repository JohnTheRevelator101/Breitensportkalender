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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

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


def extract_plz_ort(text: str) -> str:
    """
    Versucht PLZ + Ortsname aus einem Adressstring zu extrahieren.
    Robuster als das Original: toleriert fehlende Großbuchstaben am
    Ortsnamen und Satzzeichen / Ziffern im Ortsnamen.

    Strategie:
      1. Suche nach 5-stelliger PLZ, nimm alles danach bis zum ersten
         logischen Trennzeichen (Komma, Newline, oder Ende).
      2. Bereinige übrige Junk-Wörter (z.B. "Route erstellen").
    """
    if not text:
        return ""

    # 5-stellige PLZ finden
    m = re.search(r"(\d{5})\s+(.+)", text)
    if not m:
        return ""

    plz = m.group(1)
    rest = m.group(2)

    # Alles ab erstem Komma / Zeilenumbruch / "Route erstellen" abschneiden
    rest = re.split(r"[,\n]|Route erstellen|route erstellen", rest)[0]

    # Mehrfache Leerzeichen normalisieren
    ort = re.sub(r"\s+", " ", rest).strip()

    # Leere Ergebnisse abfangen
    if not ort:
        return ""

    return f"{plz} {ort}"


def geocode(query: str) -> dict | None:
    """
    Geocodiert eine Adresse via Nominatim.
    Gibt {"lat": float, "lng": float} zurück oder None.
    Hält Nominatim-Limit (max 1 Req/s) ein.
    """
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "de"},
            headers={**HEADERS, "User-Agent": "rad-net-scraper/2.0 (private research)"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        time.sleep(1.2)  # Nominatim-Limit einhalten
        if data:
            return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
    except Exception as e:
        logging.warning(f"Geocoding fehlgeschlagen für '{query}': {e}")
    return None


# -----------------------------------------------------------------------
# Detail-Scraping
# -----------------------------------------------------------------------

def scrape_detail(url: str) -> dict | None:
    """
    Ruft eine Detailseite ab und extrahiert alle relevanten Felder.
    Gibt None zurück wenn die Seite nicht abrufbar ist (→ später retry).
    """
    result = {
        "startort": "",
        "startort_adresse": "",
        "startzeit": "",
        "webseite": "",
        "landesverband": "",
    }

    try:
        time.sleep(random.uniform(2.0, 3.5))
        resp = requests.get(url, headers=HEADERS, timeout=15)

        if resp.status_code == 429:
            logging.warning(f"Rate-limit (429) bei {url} – warte 60 s")
            time.sleep(60)
            return None
        if resp.status_code != 200:
            logging.error(f"Status {resp.status_code} bei {url}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # ---- Tabellen-Rows auswerten ----
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

        # ---- Fallback: PLZ/Ort aus gesamtem Seitentext ----
        # (manche Seiten nutzen kein <tr>-Layout)
        if not result["startort"]:
            page_text = soup.get_text(separator=" ")
            result["startort"] = extract_plz_ort(page_text)

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
    logging.info("Scraper v2 gestartet")
    all_events = load_data()

    # Events die bereits vollständig verarbeitet wurden (startort ODER
    # startort_adresse vorhanden → beide Felder wurden befüllt versucht)
    processed_urls = {
        e["url"] for e in all_events
        if e.get("startort") or e.get("startort_adresse")
    }
    logging.info(f"Bereits verarbeitet: {len(processed_urls)} / {len(all_events)}")

    # ---- Phase 1: URL-Sammlung (nur wenn Liste leer) ----
    if not all_events:
        logging.info("Sammle URLs von Übersichtsseiten …")
        existing_urls = set()
        for start in range(0, 750, 30):
            params = {
                "startdate": "01.01.2026",
                "enddate": "31.12.2026",
                "lstart": str(start),
            }
            try:
                resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                logging.error(f"Übersichtsseite start={start} fehlgeschlagen: {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a", href=re.compile(r"/termine/\d{4}/"))
            for link in links:
                url = DETAIL_BASE + link.get("href")
                if url not in existing_urls:
                    existing_urls.add(url)
                    all_events.append({
                        "titel": link.get_text(strip=True)[:80],
                        "url": url,
                        "startort": "",
                    })
            time.sleep(random.uniform(1.0, 2.0))

        save_data(all_events)
        logging.info(f"{len(all_events)} Events gefunden und gespeichert.")

    # ---- Phase 2: Details & Geocoding ----
    todo = [e for e in all_events if e["url"] not in processed_urls]
    logging.info(f"Zu verarbeiten: {len(todo)} Events")

    consecutive_errors = 0  # Zähler für aufeinanderfolgende Fehler

    for i, event in enumerate(todo, 1):
        details = scrape_detail(event["url"])

        if details is None:
            consecutive_errors += 1
            logging.warning(
                f"[{i}/{len(todo)}] Fehler bei '{event['titel']}' "
                f"(Fehler in Folge: {consecutive_errors})"
            )
            if consecutive_errors >= 5:
                logging.error("5 Fehler in Folge – pausiere 2 Minuten")
                time.sleep(120)
                consecutive_errors = 0
            else:
                time.sleep(10)
            continue

        consecutive_errors = 0
        event.update(details)

        # Geocoding (nur wenn PLZ+Ort gefunden)
        if event["startort"] and not event.get("lat"):
            coords = geocode(event["startort"] + ", Deutschland")
            if coords:
                event["lat"] = coords["lat"]
                event["lng"] = coords["lng"]

        # Nach jedem Event speichern
        save_data(all_events)
        logging.info(
            f"[{i}/{len(todo)}] ✓ {event['titel'][:50]} | "
            f"Startort: '{event['startort']}'"
        )

    # ---- Abschluss-Statistik ----
    mit_startort = sum(1 for e in all_events if e.get("startort"))
    mit_coords   = sum(1 for e in all_events if e.get("lat"))
    logging.info("=== Scraping abgeschlossen ===")
    logging.info(f"Gesamt Events:      {len(all_events)}")
    logging.info(f"Mit Startort:       {mit_startort}")
    logging.info(f"Mit Koordinaten:    {mit_coords}")
    logging.info(f"Ohne Startort:      {len(all_events) - mit_startort}")


if __name__ == "__main__":
    main()
