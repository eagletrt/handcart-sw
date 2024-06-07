#!/bin/bash
cd "$(dirname "$0")"
export DISPLAY=:0
source venv/bin/activate
python src/run.py