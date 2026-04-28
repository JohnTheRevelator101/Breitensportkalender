import json
import os
import time
import random
# hier deine scrape_detail Funktion importieren

QUEUE_FILE = "queue.json"
RESULT_FILE = "events_final.json"

def main():
    # 1. Warteschlange laden
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    # 2. Bereits fertige Events laden (falls vorhanden)
    if os.path.exists(RESULT_FILE):
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            final_data = json.load(f)
    else:
        final_data = []

    # Liste der bereits verarbeiteten URLs für schnellen Abgleich
    processed_urls = {e["url"] for e in final_data}

    for event in queue:
        if event["url"] in processed_urls:
            continue  # Überspringen, wenn schon erledigt

        print(f"Verarbeite: {event['titel']}")
        
        # Details holen
        details = scrape_detail(event["url"])
        
        if details:
            event.update(details)
            final_data.append(event)
            
            # Sofort speichern nach jedem Event!
            with open(RESULT_FILE, "w", encoding="utf-8") as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
            
            # Menschliches Verhalten simulieren
            time.sleep(random.uniform(2, 4))
        else:
            print(f"Fehler bei {event['url']}, überspringe vorerst...")

if __name__ == "__main__":
    main()