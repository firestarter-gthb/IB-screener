@echo off
cd /d "%~dp0"
echo =========================================
echo Starten van de IB Momentum Screener...
echo =========================================

REM Gebruik de virtuele omgeving (.venv) als die bestaat, anders de standaard Python
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

echo.
echo Stap 1/4: Tickers verwerken en koersdata ophalen (Dit duurt even)...
%PY% ib_momentum_screener.py

echo.
echo Stap 2/4: HTML Dashboard genereren...
%PY% ib_generate_html.py

echo.
echo Stap 3/4: Top 25 Portfolio Dashboard genereren...
%PY% ib_generate_top25_html.py

echo.
echo Stap 4/4: Sector Performance Dashboard genereren...
%PY% ib_generate_sector_html.py

echo.
echo Klaar! De dashboards worden nu geopend in je browser.
start ib_screener_dashboard.html
start ib_top25_portfolio.html
start ib_sector_dashboard.html
