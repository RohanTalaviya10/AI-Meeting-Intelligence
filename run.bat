@echo off

IF NOT EXIST ".venv" (
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)

start "Backend" cmd /k ".venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
start "Frontend" cmd /k ".venv\Scripts\streamlit run frontend\app.py --server.port 8501"

echo Backend: http://localhost:8000
echo Frontend: http://localhost:8501
