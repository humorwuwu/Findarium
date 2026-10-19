from __future__ import annotations

import argparse
import os
from pathlib import Path

from . import __version__
from .app import launch
from .i18n import AUTO_LANG, resolve_setting, translate


def build_parser(lang: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="findarium", description="Findarium desktop indexer")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--headless", action="store_true", help=translate("cli.headless", lang))
    parser.add_argument("--port", type=int, default=None, help=translate("cli.port", lang))
    parser.add_argument("--library", type=Path, default=None, help=translate("cli.library", lang))
    parser.add_argument("--dev-url", default=None, help=translate("cli.dev_url", lang))
    parser.add_argument(
        "--no-embedding",
        action="store_true",
        help=translate("cli.no_embedding", lang),
    )
    parser.add_argument("--token", default=None, help=translate("cli.token", lang))
    parser.add_argument(
        "--lang",
        default=None,
        choices=[AUTO_LANG, "zh-CN", "en"],
        help=translate("cli.lang", lang),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    # The parser itself is built in the language the user asked for, so --lang
    # is read from a throwaway pre-parse before the real one.
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--lang", default=None)
    known, _ = pre.parse_known_args(argv)
    lang = resolve_setting(known.lang)

    args = build_parser(lang).parse_args(argv)
    if args.lang is not None:
        lang = resolve_setting(args.lang)
    dev_url = args.dev_url or os.environ.get("FINDARIUM_DEV_URL")
    return launch(
        headless=args.headless,
        port=args.port,
        library=args.library,
        dev_url=dev_url,
        embedding_enabled=not args.no_embedding,
        token=args.token,
        lang=lang,
    )


if __name__ == "__main__":
    raise SystemExit(main())
