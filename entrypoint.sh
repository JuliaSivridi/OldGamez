#!/bin/sh
set -e
python -m alembic upgrade head
exec python -m app.main
