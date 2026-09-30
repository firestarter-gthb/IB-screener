@echo off
echo =========================================
echo Starten van de IB Momentum Screener...
echo =========================================

echo.
echo Stap 1/2: Tickers verwerken en koersdata ophalen (Dit duurt even)...
python ib_momentum_screener.py

echo.
echo Stap 2/2: HTML Dashboard genereren...
python ib_generate_html.py

echo.
echo Klaar! Het dashboard wordt nu geopend in je browser.
start ib_screener_dashboard.html
