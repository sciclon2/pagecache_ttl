import logging


def configure_logging(log_level, log_file):
    if log_level == "DEBUG":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logger = logging.getLogger("pagecache")
    logger.setLevel(log_level)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    # Returns File descriptor for preserver it if the app is executed in daemon mode
    return file_handler.stream.fileno()
