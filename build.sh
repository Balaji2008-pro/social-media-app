#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
apt-get update && apt-get install -y ffmpeg || true

python manage.py collectstatic --no-input

python manage.py migrate