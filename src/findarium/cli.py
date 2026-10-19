from __future__ import annotations

import argparse
import os
from pathlib import Path

from . import __version__
from .app import launch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="findarium", description="Findarium desktop indexer")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--headless", action="store_true", help="只启动本地服务，不打开桌面窗口")
    parser.add_argument("--port", type=int, default=None, help="本地服务端口")
    parser.add_argument("--library", type=Path, default=None, help="指定索引库目录（开发用）")
    parser.add_argument(
        "--dev-url",
        default=None,
        help="使用 Vite 开发服务器地址（也可用 FINDARIUM_DEV_URL 环境变量）",
    )
    parser.add_argument(
        "--no-embedding",
        action="store_true",
        help="禁用语义向量，只保留关键词检索",
    )
    parser.add_argument("--token", default=None, help="固定本地 API token（调试用）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dev_url = args.dev_url or os.environ.get("FINDARIUM_DEV_URL")
    return launch(
        headless=args.headless,
        port=args.port,
        library=args.library,
        dev_url=dev_url,
        embedding_enabled=not args.no_embedding,
        token=args.token,
    )


if __name__ == "__main__":
    raise SystemExit(main())
