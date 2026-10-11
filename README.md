# Interactive Brokers (IB) Momentum Screener

Een robuuste Python-screener voor het analyseren en rangschikken van aandelen op basis van momentum, volatiliteit en sectortrends. Deze tool leest data uit een spreadsheet in, haalt live koersdata op via Yahoo Finance (2 jaar historie), berekent de scores en genereert een interactief, lokaal HTML-dashboard met de resultaten.

> 📖 **Nieuw hier? Lees de [HANDLEIDING.md](HANDLEIDING.md)**: installatie, dashboards, kolomuitleg, praktische adviezen en forward tracking.

## Kenmerken
- **Live Koersdata:** Haalt betrouwbaar dagkoersen en historische data op (yfinance).
- **Momentum Scoring:** Berekent uitgebreide metrics zoals 1M, 3M, 1Y performance, YTD, en Beta ten opzichte van de S&P500 (SPY).
- **Dynamische Ranking:** Beoordeelt aandelen op basis van een samengestelde wiskundige score: `(((1M Rank * 15%) + (3M Rank * 40%) + (1Y Rank * 45%)) * 70%) + (200 MAVG Rank * 20%) + (Scaled Sector Rank * 10%)`.
- **Shadow-kolommen (informatief, tellen NIET mee in `Total score`):** `Rank BN` is de Total score gecorrigeerd voor Beta (beta-neutrale rangschikking), `Rank 12-1` rangschikt op het 12-maands rendement zonder de laatste maand en `Rank ex-1M` is de Total score zonder de 1M-component (3M/1J herschaald). Ze staan naast `Rank all` zodat je ze live kunt vergelijken; de Top 25 en sortering blijven op `Total score` gebaseerd.
- **Snapshot-historie & forward tracking:** elke run wordt opgeslagen als `history/ib_screener_<datum>.csv`. Met `run_forward_tracker.bat` (`forward_tracker.py`) meet je achteraf hoe `Rank all` en de shadow-kolommen het in de maand(en) erna echt deden.
- **Trend Indicatie (Action):** Bepaalt automatische koop/verkoop zones (`B` voor pullback naar 20MA, `S` voor zwakte onder 50MA, en `N` voor neutraal).
- **Historische Delta:** Berekent dynamisch de delta (verschil in rangschikking) ten opzichte van exact ~30 kalenderdagen geleden in dezelfde run.
- **Sectorrank:** Aandelen zonder sector (`Unknown`), ETF's en sectoren met minder dan 3 aandelen tellen niet mee in de sectorrank en krijgen een neutrale sectorscore. Ontbrekende sectoren kun je handmatig toevoegen via `SECTOR_OVERRIDES` in `extract_tickers.py`.
- **Datakwaliteit:** De screener meldt aan het eind welke tickers zijn overgeslagen (bijv. te weinig koersdata bij Yahoo).
- **HTML Dashboard:** Exporteert alle bevindingen naar een interactief, filterbaar dashboard (`ib_screener_dashboard.html`).

## Structuur
* `data.csv`: De originele lijst van aandelen. Deze csv bevat nu enkel de benodigde kolommen (voornamelijk `Ticker`).
* `extract_tickers.py`: Parsing script dat `data.csv` opschoont, tickers (bijv. "NASDAQ:MSFT") omzet naar geldige Yahoo Finance tickers ("MSFT") en opslaat als `ib_tickers.csv`.
* `ib_momentum_screener.py`: De hoofdengine. Downloadt alle data, past de wiskundige rankings en sector-wegingen toe en genereert `ib_screener_result_final.csv`.
* `ib_generate_html.py`: Neemt de finale CSV in en bouwt hier een lokaal, visueel HTML-dashboard van.
* `analyze.py`: Bevat extra analyse- en debug-scripts. Werkt nu op de gegenereerde `ib_screener_result_final.csv`.
* `forward_tracker.py` / `run_forward_tracker.bat`: Evalueert de snapshots in `history/` tegen de werkelijke koersontwikkeling daarna.

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
