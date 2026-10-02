"""Standalone ingestion worker.

Drains the analytics events Redis stream into the analytics database on a
loop. Run alongside the API for asynchronous, scalable ingestion:

    python -m app.worker
"""

import logging
import signal
import time

from app.config import settings
from app.services.ingestion import IngestionConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5

_running = True


def _handle_shutdown(signum, frame):
    global _running
    logger.info("Shutdown signal received (%s)", signum)
    _running = False


def main():
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)
    consumer = IngestionConsumer(consumer_name=f"worker-{settings.POSTGRES_DB}")
    logger.info("Ingestion worker started (stream=%s group=%s)", settings.ANALYTICS_EVENTS_STREAM, settings.ANALYTICS_CONSUMER_GROUP)
    while _running:
        try:
            ingested = consumer.consume(max_count=500)
            if ingested:
                logger.info("Ingested %d events", ingested)
        except Exception:
            logger.exception("Ingestion cycle failed; retrying in %ss", POLL_INTERVAL_SECONDS)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        time.sleep(POLL_INTERVAL_SECONDS)
    logger.info("Ingestion worker stopped")


if __name__ == "__main__":
    main()
