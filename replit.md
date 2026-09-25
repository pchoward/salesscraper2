# Skateboard Sale Scraper

See [README.md](README.md) for filter rules, the digest report, and how to run a dry check.

Selenium scrapes sale listings from Zumiez, Skate Warehouse, CCS, and Tactics (decks, wheels, trucks, bearings) and writes `sale_items_chart.html`. Shared rules live in `filters.py` (`passes_filters`). The report lives in `report.py`. GitHub Actions uses `.github/workflows/scrape.yml` only.

```bash
python scraper.py
python test_filters.py
```
