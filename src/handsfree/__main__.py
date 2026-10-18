"""`handsfree`: run the daemon (normally as a systemd user service)."""

from __future__ import annotations

import argparse
import logging
import signal

from .config import Config
from .daemon import Daemon
from .desktop import DryRunDesktop


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="handsfree", description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="log actions instead of performing them")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.load()
    if args.dry_run:
        desktop = DryRunDesktop()
    else:
        from .desktop.omarchy import OmarchyDesktop

        desktop = OmarchyDesktop(config.section("desktop"), config.section("gaze"))

    daemon = Daemon(config, desktop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: daemon.stop())
    daemon.run()


if __name__ == "__main__":
    main()
