import asyncio
import logging
import signal
import time
from asyncio import Task
from collections import namedtuple
from pathlib import Path

import aiofiles
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


NewsInfo = namedtuple('NewsInfo', ['id', 'url', 'related_urls'])


class YCrawler:
    _BASE_URL = 'https://news.ycombinator.com'

    def __init__(self, save_path: Path, download_interval: int):
        self._save_path = save_path
        self._download_interval = download_interval
        self._running = False
        self._current_news: list[NewsInfo] = []
        self._timeout = aiohttp.ClientTimeout(total=10)
        self._yc_session: aiohttp.ClientSession | None = None
        self._related_session: aiohttp.ClientSession | None = None
        self._downloaded_urls = 0
        self._semaphore = asyncio.Semaphore(1)

    def run_forever(self) -> None:
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
        begin = time.time()
        logger.info('Checking for fresh news...')
        self._prepare_sessions()
        try:
            async with self._yc_session.get('/') as response:
                page = await response.text()
        except asyncio.TimeoutError:
            logger.info('Unable to download news page: timeout error')
        except aiohttp.ClientResponseError as e:
            logger.info('Unable to download news page: %s', e)
        else:
            news_to_download = self._get_news_to_download(page)
            logger.info('Found %s fresh news', len(news_to_download))
            tasks = []
            for news_info in news_to_download:
                tasks.append(asyncio.create_task(
                    self._download_news_one(news_info)
                ))
            await asyncio.gather(*tasks, return_exceptions=True)
            self._log_stats(news_to_download, tasks)
        finally:
            await self._finalize_sessions()
            logger.info('Done: %s sec', time.time() - begin)

    def _prepare_sessions(self) -> None:
        self._yc_session = aiohttp.ClientSession(
            self._BASE_URL,
            timeout=self._timeout,
            raise_for_status=True
        )
        self._related_session = aiohttp.ClientSession(
            timeout=self._timeout,
            raise_for_status=True
        )
        self._downloaded_urls = 0

    async def _finalize_sessions(self):
        await self._yc_session.close()
        await self._related_session.close()

    def _get_news_to_download(self, page: str) -> list[NewsInfo]:
        soup = BeautifulSoup(page, 'html.parser')
        latest_news = self._get_latest_news(soup)
        news_to_download = self._filter_latest_news(latest_news)
        return news_to_download

    def _get_latest_news(self, soup: BeautifulSoup) -> list[NewsInfo]:
        result = []
        css_selector = 'td.title > span > a'
        for news_row in soup.find_all('tr', class_='athing'):
            news_id = news_row.attrs['id']
            news_url = news_row.css.select_one(css_selector).attrs['href']
            result.append(NewsInfo(news_id, news_url, set()))
        return result

    def _filter_latest_news(
        self,
        latest_news: list[NewsInfo]
    ) -> list[NewsInfo]:
        old_ids = set([n.id for n in self._current_news])
        new_ids = set([n.id for n in latest_news])
        ids_to_update = new_ids - old_ids
        self._current_news = latest_news
        return [n for n in latest_news if n.id in ids_to_update]

    def _log_stats(
        self,
        news_to_download: list[NewsInfo],
        download_results: list[Task]
    ) -> None:
        total_news = len(news_to_download)
        downloaded_news = len([
            n
            for n in download_results
            if n.exception() is None
        ])
        total_urls = sum(len(n.related_urls) for n in news_to_download)
        logger.info(
            'Downloaded %s out of %s news',
            downloaded_news, total_news
        )
        logger.info(
            'Downloaded %s out of %s urls',
            self._downloaded_urls, total_urls
        )

    async def _download_news_one(self, news_info: NewsInfo):
        await self._get_related_urls(news_info)
        logger.info(
            'Found %s related urls for %s/item?id=%s',
            len(news_info.related_urls), self._BASE_URL, news_info.id
        )
        await self._dump_news(news_info)

    async def _get_related_urls(self, news_info: NewsInfo):
        error_msg_template = 'Unable to get news=%s comments: %s'
        async with self._semaphore:
            req_params = dict(params=dict(id=news_info.id))
            try:
                async with self._yc_session.get('/item', **req_params) as resp:
                    comments_page = await resp.text()
            except asyncio.TimeoutError:
                logger.debug(error_msg_template, news_info.id, 'timeout error')
            except aiohttp.ClientResponseError as e:
                logger.debug(error_msg_template, news_info.id, e)
            except Exception as e:
                logger.debug(error_msg_template, news_info.id, e)
            else:
                news_info.related_urls.update(
                    self._find_related_urls_in_comments(comments_page)
                )
            finally:
                await asyncio.sleep(2)

    def _find_related_urls_in_comments(self, comments_page: str) -> set[str]:
        """Extracts urls from news comments"""
        result = set()
        soup = BeautifulSoup(comments_page, 'html.parser')
        css_selector = 'div.comment > * a'
        for link in soup.css.select(css_selector):
            url = link.attrs['href']
            if not url.startswith('reply?'):
                result.add(url)
        return result

    async def _dump_news(self, news_info: NewsInfo):
        logger.info('Dumping %s', news_info.id)
        news_path = self._save_path / f'{news_info.id}'
        news_path.mkdir(parents=True, exist_ok=True)
        tasks = []
        for idx, url in enumerate(news_info.related_urls):
            tasks.append(asyncio.create_task(
                self._dump_url(url, news_path / f'url_{idx}.html', True)
            ))
        tasks.append(asyncio.create_task(
            self._dump_url(news_info.url, news_path / 'page.html', False)
        ))
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _dump_url(self, url: str, save_path: Path, stat: bool):
        try:
            if 'ycombinator' not in url:
                async with self._related_session.get(url) as response:
                    text = await response.text()
            else:
                async with self._semaphore:
                    async with self._yc_session.get(url) as response:
                        text = await response.text()
                        await asyncio.sleep(2)
        except Exception as e:
            logger.debug('URL cannot be downloaded: %s, %s', e, url)
            raise e
        else:
            async with aiofiles.open(save_path, 'w') as f:
                await f.write(text)
            if stat:
                self._downloaded_urls += 1
            logger.debug('Downloaded %s', url)
