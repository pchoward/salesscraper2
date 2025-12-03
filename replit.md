# Skateboard Sale Scraper

## Overview

A Python web scraper that tracks skateboard sale items from multiple online stores and generates a modern, interactive HTML report. The scraper runs daily via GitHub Actions and publishes the results to GitHub Pages.

## Supported Stores

- **Zumiez** - Decks, Wheels, Trucks, Bearings
- **Skate Warehouse** - Decks, Wheels, Trucks, Bearings
- **CCS** - Decks, Wheels, Trucks, Bearings
- **Tactics** - Decks, Wheels, Trucks, Bearings

## Features

### Scraping
- Selenium-based scraping with anti-bot detection measures
- Random user agent rotation
- Infinite scroll support for dynamic content
- Retry logic with exponential backoff
- Debug HTML file generation for troubleshooting

### HTML Report
- Modern, responsive design with Inter font
- Sortable tables (click column headers)
- Filter by store and product category
- Search functionality
- Discount badges with color coding (high/medium/low)
- Historical changes tracking (new items, price drops, removed items)
- Mobile-friendly layout

### Filtering Logic
- Decks: Only shows items with 10%+ discount
- Wheels: Only shows Bones, Powell, Spitfire, OJ brands
- Trucks: Only shows Independent, Indy, Ace brands (Skate Warehouse)

## Project Structure

```
├── scraper.py           # Main scraper script
├── sale_items_chart.html # Generated HTML report
├── previous_data.json   # Historical data for change tracking
├── *_debug_*.html       # Debug files (gitignored)
└── replit.md            # This file
```

## Usage

### Run Locally
```bash
python scraper.py
```

### GitHub Actions
The scraper is designed to run in CI environments with headless Chrome. Set `CI=true` environment variable to enable headless mode.

## Dependencies

- selenium
- beautifulsoup4
- fake-useragent
- webdriver-manager
- requests

## Recent Changes

- **2024-12-03**: Fixed search functionality - now case-insensitive for store/part/text
- **2024-12-03**: Performance optimization - reduced scroll attempts (8→3) and wait times by 50%+
- **2024-12-03**: Fixed workflow git push conflict with pull --rebase
- **2024-12-02**: Lowered deck discount threshold from 30% to 10%
- **2024-12-02**: Complete rewrite with improved CSS selectors for CCS and Tactics
- **2024-12-02**: Modern HTML output with sortable tables and filters
- **2024-12-02**: Added store badges and discount color coding

## Technical Notes

- Chrome/Chromium must be installed for Selenium to work
- The scraper creates temporary directories for Chrome user data
- Debug HTML files are generated for each store/part combination
- Historical data is stored in `previous_data.json` for change tracking
