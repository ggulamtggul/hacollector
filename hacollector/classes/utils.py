from __future__ import annotations

import inspect
import logging
import pathlib
import sys
from enum import Enum
from logging.handlers import RotatingFileHandler


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


STR_INFO    = 'info'
STR_DEBUG   = 'debug'
STR_WARN    = 'warn'
STR_ERROR   = 'error'
STR_CRITICAL = 'critical'
STR_NOSET   = 'noset'

CONSOLE_LOG_LEVEL = logging.INFO


class ColorLog:
    class Level(Enum):
        DEBUG       = STR_DEBUG
        INFO        = STR_INFO
        WARN        = STR_WARN
        ERROR       = STR_ERROR
        CRITICAL    = STR_CRITICAL
        NOSET       = STR_NOSET

    LOG_FORMAT = "%(asctime)s %(levelname)8s: %(message)s"

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ColorLog, cls).__new__(cls)
        return cls._instance

    def __init__(self, logger_name: str = ''):
        # Prevent re-initialization
        if hasattr(self, 'initialized'):
            return
        
        self.logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(ColorLog.LOG_FORMAT))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        self.initialized = True

    def prepare_logs(self, *args, **kwargs):
        # Deprecated: File logging handled by Supervisor/Container
        return True

    def set_level(self, level: str):
        level_map = {
            STR_DEBUG: logging.DEBUG,
            STR_INFO: logging.INFO,
            STR_WARN: logging.WARNING,
            STR_ERROR: logging.ERROR,
            STR_CRITICAL: logging.CRITICAL
        }
        self.logger.setLevel(level_map.get(level, logging.INFO))

    def set_partial_debug(self):
        pass # No-op or implement if needed

    def log(self, string: str, color: Color = Color.White, level: ColorLog.Level = Level.INFO):
        # Map ColorLog.Level to logging level
        lvl_val = logging.INFO
        if isinstance(level, ColorLog.Level):
             level_str = level.value
        else:
             level_str = str(level)

        if level_str == STR_DEBUG: lvl_val = logging.DEBUG
        elif level_str == STR_WARN: lvl_val = logging.WARNING
        elif level_str == STR_ERROR: lvl_val = logging.ERROR
        elif level_str == STR_CRITICAL: lvl_val = logging.CRITICAL
        
        # Strip color for standard logs or keep it if user wants ANSI in container logs
        # HA logs support ANSI, so we can keep it.
        if isinstance(color, Color):
            color_str = color.value
        else:
            color_str = Color.White.value
            
        msg = f"{color_str}{string}{Color.EoC.value}"
        self.logger.log(lvl_val, msg)

