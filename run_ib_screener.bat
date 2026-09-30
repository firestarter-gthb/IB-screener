@echo off
echo =========================================
echo Starten van de IB Momentum Screener...
echo =========================================

echo.
echo Stap 1/2: Tickers verwerken en koersdata ophalen (Dit duurt even)...
python ib_momentum_screener.py

echo.
echo Stap 2/3: HTML Dashboard genereren...
python ib_generate_html.py

echo.
echo Stap 3/3: Top 25 Portfolio Dashboard genereren...
python ib_generate_top25_html.py

echo.
echo Klaar! De dashboards worden nu geopend in je browser.
start ib_screener_dashboard.html
start ib_top25_portfolio.html
