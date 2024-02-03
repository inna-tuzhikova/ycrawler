import signal
from pathlib import Path
import asyncio
import logging

logger = logging.getLogger(__name__)


class YCrawler:
    def __init__(self, save_path: Path, download_interval: int):
        self._save_path = save_path
        self._download_interval = download_interval
        self._running = False

    def run_forever(self):
        if self._running:
            raise RuntimeError('Crawler is already running')
        asyncio.run(self._run_forever_async())

    async def _run_forever_async(self):
        self._running = True
        for s in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
            asyncio.get_running_loop().add_signal_handler(
                s,
                lambda: asyncio.create_task(self._shutdown())
            )
        active_downloads = []
        while True:
            active_downloads.append(asyncio.create_task(self._download_news()))
            await asyncio.sleep(self._download_interval)

            active_downloads = [d for d in active_downloads if not d.done()]
            if not self._running:
                break
        await asyncio.wait(active_downloads)

    async def _shutdown(self):
        logger.info('Gracefully shutdown: resolve all current downloads')
        self._running = False

    async def _download_news(self):
        import random
        idx = random.randint(0, 1000000)
        logger.info('Download %s is started', idx)
        await asyncio.sleep(5)
        logger.info('Downloaded %s!', idx)
