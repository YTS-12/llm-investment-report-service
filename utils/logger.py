import logging
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / "app.log"

logger = logging.getLogger("investment_report_app")
logger.setLevel(logging.INFO)

if not logger.handlers:
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
