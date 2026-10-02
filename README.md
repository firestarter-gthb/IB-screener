# Interactive Brokers (IB) Momentum Screener

Een robuuste Python-screener voor het analyseren en rangschikken van aandelen op basis van momentum, volatiliteit en sectortrends. Deze tool leest data uit een spreadsheet in, haalt live koersdata op via Yahoo Finance (tot 1 jaar terug), berekent de scores en genereert een interactief, lokaal HTML-dashboard met de resultaten.

## Kenmerken
- **Live Koersdata:** Haalt betrouwbaar dagkoersen en historische data op (yfinance).
- **Momentum Scoring:** Berekent uitgebreide metrics zoals 1M, 3M, 1Y performance, YTD, en Beta ten opzichte van de S&P500 (SPY).
- **Dynamische Ranking:** Beoordeelt aandelen op basis van een samengestelde wiskundige score: `(((1M Rank * 15%) + (3M Rank * 40%) + (1Y Rank * 45%)) * 70%) + (200 MAVG Rank * 20%) + (Scaled Sector Rank * 10%)`.
- **Trend Indicatie (Action):** Bepaalt automatische koop/verkoop zones (`B` voor pullback naar 20MA, `S` voor zwakte onder 50MA, en `N` voor neutraal).
- **Historische Delta:** Berekent dynamisch de delta (verschil in rangschikking) ten opzichte van exact ~30 kalenderdagen geleden in dezelfde run.
- **HTML Dashboard:** Exporteert alle bevindingen naar een interactief, filterbaar dashboard (`ib_screener_dashboard.html`).

## Structuur
* `data.csv`: De originele lijst van aandelen. Deze csv bevat nu enkel de benodigde kolommen (voornamelijk `Ticker`).
* `extract_tickers.py`: Parsing script dat `data.csv` opschoont, tickers (bijv. "NASDAQ:MSFT") omzet naar geldige Yahoo Finance tickers ("MSFT") en opslaat als `ib_tickers.csv`.
* `ib_momentum_screener.py`: De hoofdengine. Downloadt alle data, past de wiskundige rankings en sector-wegingen toe en genereert `ib_screener_result_final.csv`.
* `ib_generate_html.py`: Neemt de finale CSV in en bouwt hier een lokaal, visueel HTML-dashboard van.
* `analyze.py`: Bevat extra analyse- en debug-scripts. Werkt nu op de gegenereerde `ib_screener_result_final.csv`.

## 📂 Hoe te Gebruiken

1. **Screener updaten**
Draai simpelweg het `.bat` bestand om de volledige analyse uit te voeren. Het script doet het ophaalwerk en genereert de rapporten:
- `run_ib_screener.bat`

*(Let op: Het ophalen van de historische data voor alle aandelen kan 1 à 2 minuten duren. Na afloop opent de software automatisch het dashboard in je browser.)*

2. **Nieuwe lijst verwerken**
Als je handmatig `data.csv` vernieuwt met nieuwe tickers, voer dan één keer `python extract_tickers.py` uit om de lijst te structureren en namen/sectoren via Yahoo Finance op te halen, **voordat** je de screener draait.

## ⚙️ Installatie / Vereisten

Om de screener te kunnen draaien heb je het volgende nodig:

1. **Python 3.8 of nieuwer**: [Download Python](https://www.python.org/downloads/).
2. **Een webbrowser**: (Google Chrome, Edge, Safari of Firefox) om het dashboard te bekijken.
3. **Python Packages**: Installeer de vereiste pakketten in één keer door het volgende commando uit te voeren in de projectmap (of in je terminal):
   ```bash
   pip install -r requirements.txt
   ```
