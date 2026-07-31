import logging
from logging.handlers import RotatingFileHandler


def get_logger():
    logger = logging.getLogger("job_agent")

    # GUARD: without this check, every module that calls get_logger()
    # adds ANOTHER pair of handlers to the same shared logger object
    # (logging.getLogger("job_agent") always returns the same instance),
    # causing every log line to print once per import. Only configure
    # handlers the first time this logger is set up.
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        fmt = "%(asctime)s [%(levelname)s] %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(fmt, datefmt))
        logger.addHandler(ch)

        fh = RotatingFileHandler("job_agent.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(fmt, datefmt))
        logger.addHandler(fh)

    return logger