# Handleiding IB Momentum Screener

Deze handleiding legt uit hoe je de screener installeert, draait, de dashboards leest en de uitkomst verstandig gebruikt. De adviezen in hoofdstuk 5 zijn gebaseerd op een backtest over 10 jaar historische data (2017–2026).

---

## Inhoud
1. [Wat doet de screener?](#1-wat-doet-de-screener)
2. [Eenmalige installatie](#2-eenmalige-installatie)
3. [De screener draaien](#3-de-screener-draaien)
4. [De dashboards lezen](#4-de-dashboards-lezen)
5. [Hoe gebruik je de uitkomst? (praktische adviezen)](#5-hoe-gebruik-je-de-uitkomst-praktische-adviezen)
6. [Forward tracking: de screener live volgen](#6-forward-tracking-de-screener-live-volgen)
7. [Onderhoud: tickers en sectoren](#7-onderhoud-tickers-en-sectoren)
8. [Problemen oplossen](#8-problemen-oplossen)
9. [Bestandsoverzicht](#9-bestandsoverzicht)
10. [Belangrijke kanttekeningen](#10-belangrijke-kanttekeningen)

---

## 1. Wat doet de screener?

De screener rangschikt ~290 aandelen uit `data.csv` op **momentum**: aandelen die de afgelopen maanden en het afgelopen jaar het sterkst zijn gestegen, komen bovenaan.

Per aandeel wordt een **Total score** berekend. **Hoe lager de score, hoe beter**: `Rank all = 1` is het sterkste aandeel.

| Onderdeel | Effectief gewicht | Wat het meet |
| :--- | :--- | :--- |
| Rank 1M | 10,5% | Rendement afgelopen maand |
| Rank 3M | 28% | Rendement afgelopen 3 maanden |
| Rank 1 Jaar | 31,5% | Rendement afgelopen 12 maanden |
| Rank 200 MAVG | 20% | Hoe ver de koers boven het 200-daags gemiddelde staat |
| Sectorrank | 10% | Hoe sterk de sector van het aandeel is |

Formule: `(((Rank1M × 15%) + (Rank3M × 40%) + (Rank1J × 45%)) × 70%) + (Rank200MA × 20%) + (Sectorrank × 10%)`

---

## 2. Eenmalige installatie

1. Installeer **Python 3.10 of nieuwer** ([python.org](https://www.python.org/downloads/)). Vink bij de installatie *"Add Python to PATH"* aan.
2. Open PowerShell in de projectmap en maak een virtuele omgeving met de benodigde pakketten:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
3. Klaar. De `.bat`-bestanden gebruiken automatisch `.venv` als die bestaat.

---

## 3. De screener draaien

**Dubbelklik op [`run_ib_screener.bat`](run_ib_screener.bat).** Dat doet in ongeveer 1–2 minuten:

1. Koersdata ophalen bij Yahoo Finance (2 jaar historie) en alle scores berekenen.
2. De resultaten opslaan in `ib_screener_result_final.csv`.
3. **Een snapshot met datum opslaan** in de map `history/` (zie hoofdstuk 6).
4. De drie dashboards genereren en openen in je browser.

> **Let op de meldingen aan het eind van stap 1.** De screener meldt welke tickers zijn overgeslagen, bijvoorbeeld *"ET (slechts 8 koersen)"*. Dat ligt meestal aan Yahoo (tickerwissel of datastoring) en lost zich vaak vanzelf op.

**Hoe vaak?** Minimaal **1× per maand**, bij voorkeur rond dezelfde dag (bijv. de eerste handelsdag van de maand). Vaker mag, maar meer dan 1× per week voegt weinig toe: het signaal verandert langzaam.

---

## 4. De dashboards lezen

### 4.1 `ib_screener_dashboard.html` – alle aandelen

Volledige lijst, standaard gesorteerd op `Rank all`. Klik op een kolomtitel om te sorteren en gebruik het filtervak onder de titel om te filteren. Met **Filters wissen** begin je opnieuw. Ranks ≤ 10 worden groen gemarkeerd.

| Kolom | Betekenis |
| :--- | :--- |
| **Action** | `B` = koers dicht bij 20-daags gemiddelde (rustig instapmoment), `S` = koers onder 50-daags gemiddelde (zwakte), `N` = neutraal |
| **Rank all** | Officiële rangschikking op Total score (1 = beste) |
| **Rank all past** / **Delta** | Rank van ~1 maand geleden en de verandering (positief = gestegen) |
| Rank shortterm / longterm | Oude deelrankings (alleen ter informatie) |
| **Rank BN** | *Shadow-kolom*: Total score gecorrigeerd voor Beta, dus zonder het effect van "gewoon meer risico" |
| **Rank 12-1** | *Shadow-kolom*: 12-maands rendement zonder de laatste maand (klassiek academisch momentum) |
| **Rank ex-1M** | *Shadow-kolom*: Total score **zonder** de 1M-component |
| Trend | `Bullish` = koers boven 200-daags gemiddelde |
| Beta | Gevoeligheid voor de markt (S&P 500). 1,5 = beweegt gemiddeld 1,5× zo hard als de markt |
| Last month / 3 months / year / YTD | Rendementen |
| 200 avg | Afstand tot het 200-daags gemiddelde |
| Z-score 20MA | Afstand tot het 20-daags gemiddelde in standaarddeviaties |
| Sharpe Ratio / Efficiency Score | Rendement per eenheid risico / hoe "rechtlijnig" de koers steeg (12 mnd) |
| Rank 1M … Rank 200 MAVG | De losse onderdelen van de Total score |
| Total score | De score zelf (lager = beter) |
| Total score incl beta | Variant met een kleine straf voor hoge beta (informatief) |
| Sector momentum rank | Rank van de sector (1 = sterkste sector) |

> **Shadow-kolommen tellen niet mee** in de Total score, de sortering of de Top 25. Ze staan er alleen om live te vergelijken.

### 4.2 `ib_top25_portfolio.html` – Top 25

De 25 aandelen met de beste Total score **na filters**: Trend = Bullish, Action ≠ S, Sharpe ≥ 0,8 en Rank longterm ≤ 100.

### 4.3 `ib_sector_dashboard.html` – sectoren

Rangschikking van GICS-sectoren op het gemiddelde momentum van hun aandelen, met het aantal aandelen per sector en de verandering t.o.v. ~30 dagen geleden. Sectoren met minder dan 3 aandelen, ETF's en `Unknown` tellen niet mee.

---

## 5. Hoe gebruik je de uitkomst? (praktische adviezen)

De adviezen hieronder volgen uit de backtest van 10 jaar. **Ze zijn geen garantie**; zie hoofdstuk 10.

| # | Advies | Waarom |
| :--- | :--- | :--- |
| 1 | **Gebruik de Total score / Rank all als hoofdcriterium.** Een groep van ~20–25 aandelen bovenin is robuuster dan 3–5 favorieten. | De rangschikking werkt gemiddeld over veel aandelen. Per aandeel is het signaal zwak en zijn uitschieters toeval. |
| 2 | **Houd posities langer vast, bijv. ~3 maanden, en ververs in tranches** (elke maand ⅓ van de portefeuille vervangen). | Het signaal blijft ~6 maanden geldig. In de backtest: Sharpe 1,21 → 1,40, maximale daling −27% → −19% en half zoveel transacties. |
| 3 | **Wees je bewust van Beta.** De top van de lijst heeft gemiddeld een beta van ~1,2–1,5. | Een groot deel van het rendement is "meer markt". In een dalende markt daalt de Top 25 harder dan de index. Kijk ter vergelijking naar `Rank BN`. |
| 4 | **Zie de Top 25-filters en Action niet als extra voordeel.** | Trend-, Sharpe-, Action- en Rank-longterm-filters verbeterden het resultaat in de backtest niet aantoonbaar. Action ≠ S filtert soms juist goede dips weg. |
| 5 | **Gebruik Delta niet als koopsignaal.** | Een sterke stijger in rank voorspelde in de backtest niets extra. |
| 6 | **Pas de gewichten van de Total score niet aan op basis van recente prestaties.** | Welke horizon (3M of 1J) het best werkt, wisselt per marktfase. Optimaliseren op het verleden werkte out-of-sample slechter dan de huidige mix. |
| 7 | **Spreid over sectoren** als de top sterk in één sector zit. | De sectorcomponent voegt weinig voorspellende waarde toe; concentratie vergroot vooral het risico. |

Achtergrond: de onderzoeksrapporten uit de backtest-analyse (backtest review v2, verbeteronderzoek en de Total score-analyse).

---

## 6. Forward tracking: de screener live volgen

Een backtest kijkt terug. Of de screener **echt** werkt, zie je pas door hem vooruit te volgen. Daarom wordt elke run automatisch opgeslagen als `history/ib_screener_<datum>.csv`.

### Zo werkt het
1. Draai de screener **minimaal 1× per maand** (hoofdstuk 3). De snapshots verzamelen zich vanzelf.
2. Dubbelklik **1× per maand** op [`run_forward_tracker.bat`](run_forward_tracker.bat). Het script haalt de koersen ná elke snapshot op en vergelijkt:
   - **Rank all** (officieel), **Rank ex-1M**, **Rank BN**, **Rank 12-1** en de **Dashboard Top 25** (met filters).
3. Het resultaat staat in `forward_tracking_result.md`, met details per snapshot in `forward_tracking_detail.csv`.

Een snapshot telt pas mee als er **21 handelsdagen** (~1 maand) verstreken zijn. Snapshots die minder dan een maand uit elkaar liggen, tellen maar één keer mee (anders telt dezelfde koersbeweging dubbel).

Optioneel: `forward_tracker.py --horizon 63` meet 3 maanden vooruit (past bij advies 2).

### Hoe lees je het?

| Maat | Betekenis | Goed als… |
| :--- | :--- | :--- |
| **Gem. IC** | Rangcorrelatie tussen rank en het rendement daarna | > 0 (in de backtest ~0,02) |
| **Top-25 excess** | Rendement Top 25 minus het gemiddelde van alle aandelen | > 0 |
| **Verschil vs Rank all** | Doet een shadow-kolom het beter dan de officiële score? | Positief **en** \|t\| > 2 |

> **Geduld:** trek pas conclusies na **24–36 maanden**. Daarvoor is het vooral ruis. Een variant (bijv. Rank ex-1M) is pas een vervanger als hij over die periode duidelijk (t > 2) beter is op zowel IC als Top-25-rendement.

---

## 7. Onderhoud: tickers en sectoren

### Nieuwe of gewijzigde aandelenlijst
1. Vervang/bewerk `data.csv` (kolom `Ticker`, bijv. `NASDAQ:MSFT` of `MSFT`).
2. Draai één keer:
   ```powershell
   .\.venv\Scripts\python.exe extract_tickers.py
   ```
   Dit maakt `ib_tickers.csv` met Yahoo-tickers, namen en sectoren (duurt 1–2 minuten).
3. Draai daarna de screener.

Aandelenklassen worden automatisch omgezet (`BRK.B` → `BRK-B`). ETF's krijgen sector `ETF` en tellen niet mee in de sectorrank.

### Ontbrekende sector
Meldt `extract_tickers.py` tickers zonder sector (`Unknown`)? Voeg ze dan toe aan `SECTOR_OVERRIDES` bovenin `extract_tickers.py`:
```python
SECTOR_OVERRIDES = {
    'FISV': ('Technology', 'Information Technology Services'),
    'XYZ':  ('Industrials', 'Specialty Industrial Machinery'),
}
```

---

## 8. Problemen oplossen

| Probleem | Oplossing |
| :--- | :--- |
| `python` wordt niet herkend | Python opnieuw installeren met *"Add to PATH"*, of de `.venv` aanmaken (hoofdstuk 2) |
| `ModuleNotFoundError` | `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` |
| "Data ophalen mislukt" | Internetverbinding controleren; Yahoo is soms tijdelijk onbereikbaar. Na een paar minuten opnieuw proberen |
| Ticker overgeslagen ("slechts X koersen") | Tickerwissel of probleem bij Yahoo. Controleer de ticker op finance.yahoo.com en pas zo nodig `data.csv` aan |
| Aandeel heeft sector `Unknown` | Zie hoofdstuk 7, `SECTOR_OVERRIDES` |
| Dashboard toont oude data | Controleer of stap 1 van de `.bat` zonder fouten eindigde; ververs de browser (Ctrl+F5) |
| Forward tracker: "Nog geen snapshot is oud genoeg" | Normaal in de eerste maand. Blijf de screener draaien |

---

## 9. Bestandsoverzicht

| Bestand | Doel |
| :--- | :--- |
| `run_ib_screener.bat` | **Start hier**: draait de screener en opent de dashboards |
| `run_forward_tracker.bat` | Maandelijkse forward-evaluatie van de snapshots |
| `data.csv` → `extract_tickers.py` → `ib_tickers.csv` | Aandelenlijst opschonen en sectoren ophalen |
| `ib_momentum_screener.py` | Rekent alle scores uit |
| `ib_generate_*.py` | Bouwen de drie HTML-dashboards |
| `ib_screener_result_final.csv` / `ib_sector_result.csv` | Uitkomst van de laatste run |
| `history/ib_screener_<datum>.csv` | Snapshot per run (voor forward tracking) |
| `forward_tracker.py` | Evalueert de snapshots tegen de echte koersontwikkeling |
| `backtester_*.py`, `backtest_dataset_*.csv` | Onderzoek/backtests (niet nodig voor dagelijks gebruik) |

---

## 10. Belangrijke kanttekeningen

- **Geen beleggingsadvies.** De screener is een hulpmiddel om ideeën te selecteren, geen koop- of verkoopadvies.
- **Het signaal is zwak.** In de backtest was de voorspellende waarde positief maar niet statistisch significant, en een groot deel van het rendement kwam uit marktrisico (beta).
- **Survivorship bias:** de backtest gebruikt de huidige aandelenlijst. Bedrijven die in het verleden zijn weggevallen, ontbreken, waardoor de backtest waarschijnlijk te rooskleurig is.
- **Uitschieters:** een deel van het historische rendement kwam van een handvol aandelen (bijv. GME, ENPH, SMCI) en uit 2020.
- **Kosten en belasting** zijn in de backtest maar beperkt meegenomen. Veel handelen kost rendement; daarom advies 2.
- **Data van Yahoo Finance** is gratis en meestal goed, maar niet foutloos. Controleer opvallende uitschieters voordat je handelt.
