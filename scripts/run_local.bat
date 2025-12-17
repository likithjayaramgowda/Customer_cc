\
@echo off
setlocal
if "%LOCAL_EVENT_PATH%"=="" set LOCAL_EVENT_PATH=sample_event.json
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
endlocal
