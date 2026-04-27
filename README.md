# Radkalender 🚲

Interaktive Karte aller Breitensport-Radsporttermine in Deutschland.  
Daten von [rad-net.de Breitensportkalender](https://breitensport.rad-net.de/breitensportkalender/) – nur verlinkt, nicht kopiert.

## Features
- Interaktive Leaflet-Karte mit OpenStreetMap
- Filter nach Typ (RTF, Marathon, CTF, Gravel...)
- Filter nach Datum
- Klick öffnet Original-Seite auf rad-net.de
- Automatische Aktualisierung jeden Tag um 3 Uhr nachts

## Struktur
- `index.html` – Die Webseite
- `scraper.py` – Holt die Termine von rad-net
- `events.json` – Wird automatisch befüllt
- `.github/workflows/scrape.yml` – Automatisierung

## Setup
1. Repository auf GitHub als öffentlich anlegen
2. GitHub Pages aktivieren (Settings → Pages → Branch: main)
3. Einmal manuell den Workflow starten (Actions → "Termine aktualisieren" → Run workflow)
