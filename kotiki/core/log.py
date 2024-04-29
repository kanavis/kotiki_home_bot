import logging
import sys


def setup_logging(debug: bool, quiet: bool):
    level = logging.DEBUG if debug else logging.WARNING if quiet else logging.INFO

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)

    for logger in logging.getLogger("kotiki"), logging.getLogger("__main__"):
        logger.setLevel(level)
        logger.addHandler(stdout_handler)
