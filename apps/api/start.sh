#!/bin/bash
export PYTHONPATH=/app:$PYTHONPATH
export GIT_PYTHON_REFRESH=quiet
uvicorn main:app --host 0.0.0.0 --port $PORT
