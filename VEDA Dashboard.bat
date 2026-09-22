@echo off
cd /d "C:\Users\HP\Desktop\veda-merged"
call .venv\Scripts\activate.bat
python scripts\run_dashboard.py
pause