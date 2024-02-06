from argparse import ArgumentParser
from pathlib import Path

from ycrawler.crawler import run_crawler


def main() -> None:
    parser = ArgumentParser('Downloads news from `news.ycombinator.com`')
    parser.add_argument('save_path', type=Path,
                        help='Path to save downloaded news')
    parser.add_argument('download_interval', type=int,
                        help='Period between new entries check, sec')
    parser.add_argument('--verbose', action='store_true',
                        help='If specified runs logging in debug mode')
    parser.add_argument('--log_output', default=None,
                        help='Logs path. If not specified stdout is used')

    args = parser.parse_args()

    assert not args.save_path.is_file(), (
        f'Invalid output folder, file exists: {args.save_path}. '
        f'Provide new or existing directory'
    )
    args.save_path.mkdir(parents=True, exist_ok=True)

    assert args.download_interval > 0, (
        f'Expected positive int, got {args.download_interval}'
    )
    run_crawler(
        args.save_path, args.download_interval, args.verbose, args.log_output
    )


if __name__ == '__main__':
    main()
