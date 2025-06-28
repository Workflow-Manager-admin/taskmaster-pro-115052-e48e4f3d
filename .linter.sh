#!/bin/bash
cd /home/kavia/workspace/code-generation/taskmaster-pro-115052-e48e4f3d/flask_api_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

