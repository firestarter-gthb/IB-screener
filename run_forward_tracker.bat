@echo off
cd /d "%~dp0"
REM Forward tracking: hoe deden de opgeslagen snapshots (map history\) het daarna echt?
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
%PY% forward_tracker.py %*
if exist forward_tracking_result.md start "" forward_tracking_result.md
pause
