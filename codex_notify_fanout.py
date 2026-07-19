#!/usr/bin/env python3
"""Deliver a Codex completion event to existing local and Telegram notifiers."""

import subprocess
import sys


COMPUTER_USE_CLIENT = (
    "/Users/ruslan_zeynalov/.codex/computer-use/Codex Computer Use.app/"
    "Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/"
    "SkyComputerUseClient"
)
TELEGRAM_NOTIFIER = "/Users/ruslan_zeynalov/.codex/telegram_notify.py"


def _run(command, timeout):
    try:
        subprocess.run(
            command,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def main():
    if len(sys.argv) != 2:
        return 0

    event = sys.argv[1]
    _run([COMPUTER_USE_CLIENT, "turn-ended", event], timeout=5)
    _run(["/usr/bin/python3", TELEGRAM_NOTIFIER, event], timeout=15)
    return 0


if __name__ == "__main__":
    sys.exit(main())
