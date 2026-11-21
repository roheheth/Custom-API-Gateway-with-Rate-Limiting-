import logging
from logging.handlers import RotatingFileHandler
import os
import datetime

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# We only keep the custom timestamp formatter
class ISO8601Formatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc)
        return dt.isoformat(timespec='milliseconds').replace("+00:00", "Z")

# We use the ISO8601Formatter directly instead of WinstonStyleFormatter
formatter = ISO8601Formatter(
    fmt="%(asctime)s %(levelname)s: %(message)s"
)

logger = logging.getLogger("gateway")
logger.setLevel(logging.INFO)
logger.propagate = False #prevents from handling twice (eg: root and gateway)

# Console handler
console_handler = logging.StreamHandler() #writes logs to console
console_handler.setFormatter(formatter) # decides how the log should look 
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler) #this connects the handler to logger

# Combined log handler
combined_handler = RotatingFileHandler("logs/combined.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
combined_handler.setFormatter(formatter)
combined_handler.setLevel(logging.INFO)
logger.addHandler(combined_handler)

# Error log handler
error_handler = RotatingFileHandler("logs/error.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8")
error_handler.setFormatter(formatter)
error_handler.setLevel(logging.ERROR)
logger.addHandler(error_handler)