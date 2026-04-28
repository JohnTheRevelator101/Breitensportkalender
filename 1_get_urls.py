# ... (deine Scraping-Logik für die Übersicht)
all_found_events = scrape_overview_pages() 
with open("queue.json", "w", encoding="utf-8") as f:
    json.dump(all_found_events, f, indent=2)
print(f"{len(all_found_events)} URLs in Warteschlange gespeichert.")