# Cloud image — always-on Telegram bot + data pipeline (Mac can be off).
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt \
    && pip install --no-cache-dir git+https://github.com/Definedge-Securities/pyintegrate.git

COPY bnf_research/ bnf_research/
COPY signal_engine/ signal_engine/
COPY config/ config/
COPY research/ research/
COPY feature_factory.py update_pipeline.py view_engine.py telegram_bot.py telegram_notify.py live_tick_feed.py ./
COPY scripts/ scripts/
COPY cloud/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
