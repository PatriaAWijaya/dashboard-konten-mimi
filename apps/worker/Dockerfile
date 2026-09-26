FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Dependensi backend (apps/api) + dependensi khusus worker (apscheduler).
COPY apps/api/requirements.txt /tmp/api-requirements.txt
COPY apps/worker/requirements.txt /tmp/worker-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt -r /tmp/worker-requirements.txt

# Kode backend (paket `app`) dan worker (paket `worker`).
COPY apps/api /srv/apps/api
COPY apps/worker /srv/apps/worker

# Agar `python -m worker.main` menemukan paket `worker` (di /srv/apps) dan
# `from app... import ...` menemukan backend (di /srv/apps/api). Cadangan:
# bootstrap sys.path di worker/main.py.
ENV PYTHONPATH=/srv/apps:/srv/apps/api

WORKDIR /srv
CMD ["python", "-m", "worker.main"]
