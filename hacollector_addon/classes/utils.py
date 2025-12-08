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

    LOG_FORMAT = "%(asctime)s %(levelname)8s:%(message)s"

    # use Singleton Class Design pattern
    def __new__(cls, _=''):
        if not hasattr(cls, 'instance'):
            cls.instance = super(ColorLog, cls).__new__(cls)
        return cls.instance

    def __init__(self, logger_name: str = ''):
        if logger_name != '':
            self.debug_string_length = 25
            self.log_stream_handler = logging.StreamHandler(sys.stderr)
            self.log_stream_handler.setFormatter(logging.Formatter(ColorLog.LOG_FORMAT))
            self.log_stream_handler.setLevel(CONSOLE_LOG_LEVEL)
            self.partial_debug: bool = False

            if logger_name == 'CONSOLE':
                self.logger = logging.getLogger(None)
            else:
                self.logger = logging.getLogger(logger_name)

            self.logger.addHandler(self.log_stream_handler)
            logging.getLogger("chardet.charsetprober").disabled = True

            self.logger.setLevel(CONSOLE_LOG_LEVEL)

    @property
    def _caller(self):
        _, line_number, func_name, _ = self.logger.findCaller()
        return (func_name, line_number)

    def prepare_logs(
        self,
        root: pathlib.Path,
        sub_path: str   = 'log',
        file_name: str  = 'logfile.log',
        file_size: int  = 1024 * 1000,
        file_counts: int = 10
    ):
        '''
        prepare logging environment.

        Arguments :
            root        : path of root dir
            sub_path    : path of log dir
            file_name   : log file name
            file_size   : max file size of one log file
            file_counts : max file counts of log files

        Returns :
            True        : if all set is ok
            False       : if something wrong
        '''
        try:
            if file_name == '':
                return False

            log_dir: pathlib.Path = root
            if sub_path != '':
                log_dir = root / 'log'
                log_dir.mkdir(exist_ok=True)
            log_file = log_dir / file_name

            self.log_file_handler = RotatingFileHandler(
                filename=log_file, maxBytes=file_size, backupCount=file_counts, encoding='utf-8'
            )
            self.log_file_handler.setFormatter(logging.Formatter(ColorLog.LOG_FORMAT))
            self.log_file_handler.setLevel(logging.DEBUG)
            self.logger.addHandler(self.log_file_handler)

        except Exception as e:
            print(f"Error in preparing log. [{e}]")
            return False
        return True

    def get_logger(self):
        return self.logger

    def set_minimum(self):
        self.logger.setLevel(logging.ERROR)

    def set_partial_debug(self):
        self.partial_debug = True

    def set_level(self, level: str):
        # current logging module accept string level. but, for compatiility. - KKS
        if level == STR_INFO:
            self.logger.setLevel(logging.INFO)
        elif level == STR_DEBUG:
            self.logger.setLevel(logging.DEBUG)
        elif level == STR_WARN:
            self.logger.setLevel(logging.WARNING)
        else:
            self.logger.setLevel(logging.ERROR)

    def adjust_info_length(self, debug_info: str) -> str:
        length = len(debug_info)
        if len(debug_info) > self.debug_string_length:
            two_str = debug_info.split(':')
            len2 = len(two_str[1])
            debug_info = debug_info[:self.debug_string_length - (len('..:') + len2)] + '..:' + two_str[1]
        else:
            debug_info = debug_info + ' ' * (self.debug_string_length - length)
        return debug_info

    def log(self, string: str, color: Color = Color.White, level: ColorLog.Level = Level.INFO):
        '''
        ouput log with ANSI color

        Arguments :
            string  : str for log output
            color   : color of log string.
            level   : level of loggin. enum or string value is valid

        Return :
            None    : but, logger color is changed.
        '''
        if isinstance(color, Color):
            if color in set(item.value for item in Color) or color in Color:
                color_str = Color(color).value
            else:
                color_str = Color.White.value
        else:
            color_str = Color.White.value

        if level not in set(item.value for item in ColorLog.Level) and level not in ColorLog.Level:
            fn = self.logger.info
        else:
            fn_str = f"self.logger.{ColorLog.Level(level).value}"
            fn = eval(fn_str)

        debug_info = f"{inspect.stack()[1].function}:{inspect.stack()[1].lineno}"
        debug_info = '[' + self.adjust_info_length(debug_info) + '] '

        fn(f'{debug_info}{color_str}{string}{Color.EoC.value}')
