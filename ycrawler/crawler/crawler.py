from pathlib import Path


class YCrawler:
    def __init__(self, save_path: Path, download_interval: int):
        self._save_path = save_path
        self._download_interval = download_interval

    def run_forever(self):
        print('I\'m running forever!!!')
        while True:
            pass

    def shutdown(self):
        pass
