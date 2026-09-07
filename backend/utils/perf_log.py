import json
import logging
from datetime import datetime
from pathlib import Path

from logging.handlers import RotatingFileHandler

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "performance.log"

_logger = logging.getLogger("detecto.performance")
_logger.setLevel(logging.INFO)

if not _logger.handlers:
    _LOG_DIR.mkdir(exist_ok=True)
    _handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _logger.addHandler(_handler)


def log_detection(count, average_confidence, inference_time):
    """Append a single detection record (JSON) to the performance log."""
    _logger.info(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "count": count,
        "average_confidence": round(average_confidence, 4),
        "inference_time": round(inference_time, 4),
    }))