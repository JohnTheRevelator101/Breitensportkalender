# Radkalender 🚲

Interaktive Karte aller Breitensport-Radsporttermine in Deutschland.  
Daten von [rad-net.de Breitensportkalender](https://breitensport.rad-net.de/breitensportkalender/) – nur verlinkt, nicht kopiert.

## Features
- Interaktive Leaflet-Karte mit OpenStreetMap, Marker-Clustering in dichten Regionen
- Dark Mode (per CSS-Filter auf die OSM-Kacheln, ohne externen Kartendienst/API-Key)
- Filter nach Typ (RTF, Marathon, CTF, Gravel...) und Datum
- Terminliste auch auf dem Handy nutzbar (ausklappbares Panel)
- Klick auf einen Termin öffnet die Original-Seite auf rad-net.de; Hover hebt den zugehörigen Marker hervor
- "Standort anzeigen"-Button mit 100-km-Umkreis

## Struktur
- `index.html` – die Webseite (HTML/CSS/JS in einer Datei)
- `events.json` – die Termindaten
- `geocode_repair.py` – Hilfsskript: setzt fälschlich auf einen Fallback-Punkt gesetzte
  Koordinaten zurück und geocodiert fehlende/falsche Startorte neu (inkl. Schweizer/
  österreichischer Adressen ohne deutsches PLZ-Format) über Nominatim
- `CNAME`, `robots.txt`, `sitemap.xml`, `favicon.ico` – GitHub-Pages- und SEO-Grundlagen

> Hinweis: `events.json` wird aktuell manuell gepflegt/hochgeladen. Ein automatischer
> täglicher Scraper (z. B. per GitHub Actions) ist noch nicht Teil dieses Repos, wäre
> aber eine sinnvolle nächste Ausbaustufe.

## Setup
1. Repository auf GitHub als öffentlich anlegen
2. GitHub Pages aktivieren (Settings → Pages → Branch: main)
3. `events.json` aktuell halten, z. B. mit `python geocode_repair.py` nach dem
   Einspielen neuer Termine, um Geocoding-Fehler zu bereinigen
