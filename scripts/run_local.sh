#!/usr/bin/env bash
set -euo pipefail
export LOCAL_EVENT_PATH="${LOCAL_EVENT_PATH:-sample_event.json}"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
