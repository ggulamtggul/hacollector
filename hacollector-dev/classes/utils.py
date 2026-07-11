from __future__ import annotations

import logging
import sys
from enum import Enum

# dict of ANSI color set
class Color(Enum):
    EoC       = '\033[0m'        # End of color
    Red       = '\033[31m'
    Green     = '\033[32m'
    Yellow    = '\033[33m'
    Blue      = '\033[34m'
    Magenta   = '\033[35m'
    Cyan      = '\033[36m'
    White     = '\033[37m'
    
class CustomFormatter(logging.Formatter):
    """Logging Formatter to add colors and count warning / errors"""

    format_str = "%(asctime)s %(levelname)8s: %(message)s"

    FORMATS = {
        logging.DEBUG: Color.White.value + format_str + Color.EoC.value,
        logging.INFO: Color.Green.value + format_str + Color.EoC.value,
        logging.WARNING: Color.Yellow.value + format_str + Color.EoC.value,
        logging.ERROR: Color.Red.value + format_str + Color.EoC.value,
        logging.CRITICAL: Color.Red.value + format_str + Color.EoC.value,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.format_str)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def setup_logging(level_name: str = 'INFO'):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO) # Default capture level

    # Remove existing handlers to avoid duplicates during reload/tests
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    
    # Map string level to logging constant
    level_map = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warn': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
        'noset': logging.NOTSET
    }
    target_level = level_map.get(level_name.lower(), logging.INFO)
    ch.setLevel(target_level)
    logger.setLevel(target_level)

    ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)


