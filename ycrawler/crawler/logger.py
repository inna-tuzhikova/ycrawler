import logging
from pathlib import Path


def init_logging(log_output: Path | None, verbose: bool) -> None:
    """Sets basic logging settings

    Args:
        log_output (Path | None): path to log file. If is None, stdout is used
        verbose (bool): if True sets log level to DEBUG, INFO otherwise
    """
    logging.basicConfig(
        filename=log_output,
        level=logging.DEBUG if verbose else logging.INFO,
        format='[%(asctime)s] %(levelname).1s %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S',
    )
