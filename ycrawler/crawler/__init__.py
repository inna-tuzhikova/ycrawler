from pathlib import Path
import logging

from ycrawler.crawler.crawler import YCrawler
from ycrawler.crawler.logger import init_logging


def run_crawler(
    save_path: Path,
    download_interval: int,
    verbose: bool,
    log_output: Path | None
) -> None:
    init_logging(log_output, verbose)
    log = logging.getLogger(__name__)
    log.info('YCrawler is about to start!')

    crawl = YCrawler(save_path, download_interval)
    try:
        crawl.run_forever()
    except KeyboardInterrupt:
        log.info('Shutting down crawler...')
        crawl.shutdown()
        log.info('Crawler is shut down')
    except Exception as e:
        log.exception('Unexpected error %s', e)
        exit(1)
