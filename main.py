#!/usr/bin/env python3
"""
Joint Focus - Terminal-Produktivitäts-Timer.

Start:
    python3 main.py

Statt eines schnöden Fortschrittsbalkens brennt während der Fokuszeit
ein Joint langsam ab. Jede vollständig durchgelaufene Session gibt
einen "freigespielten" Joint, der später eingelöst werden kann.
"""

import curses
import sys

from joint_focus.ui import run


def main() -> int:
    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
