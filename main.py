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

from joint_focus.colors import reset_terminal_background, set_terminal_background
from joint_focus.ui import run


def main() -> int:
    set_terminal_background()
    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass
    finally:
        reset_terminal_background()
    return 0


if __name__ == "__main__":
    sys.exit(main())
