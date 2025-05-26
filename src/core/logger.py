import json
import logging


class Logger:
    """Class Config For Logger"""

    def __init__(
        self,
        logger_name: str,
        log_file: str = "app.log",
        log_level: int = logging.DEBUG,
    ):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(log_level)

        class JsonFormatter(logging.Formatter):
            def format(self, record):
                """Formats only the message part as JSON if applicable."""
                try:
                    if isinstance(record.msg, (dict, list)):
                        record.msg = json.dumps(record.msg, indent=4)
                except Exception:
                    pass

                return super().format(record)

        self.formatter = JsonFormatter(
            "\n%(levelname)s: (%(name)s) == %(message)s [%(lineno)d]"
        )

        # File handler
        # self.file_handler = logging.FileHandler(log_file)
        # self.file_handler.setFormatter(self.formatter)
        # self.logger.addHandler(self.file_handler)
        #
        # # Console handler
        self.console_handler = logging.StreamHandler()
        self.console_handler.setFormatter(self.formatter)
        self.logger.addHandler(self.console_handler)

    def get_logger(self):
        return self.logger
