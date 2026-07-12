"""
Farbpaletten für Joint Focus.

Nutzt, falls verfügbar, 256-Farben (xterm-256color) für schöne Pastelltöne.
Fällt sonst sauber auf die 8 Standardfarben von curses zurück.
"""

import curses

# --- Farbpaar-IDs (werden in init_colors() befüllt) ---
TITLE = 1
MENU_NORMAL = 2
MENU_SELECTED = 3
MENU_DISABLED = 4
COUNTER = 5
JOINT_PAPER = 6
JOINT_ASH = 7
JOINT_CHERRY_HOT = 8
JOINT_CHERRY_COOL = 9
JOINT_FILTER = 10
SMOKE = 11
ASH_FLAKES = 12
BORDER = 13
SUCCESS = 14
INFO = 15
TIMER_TEXT = 16
PASTEL_YELLOW = 17
SUBTITLE = 18


def init_colors() -> None:
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        pass

    has_256 = curses.COLORS >= 256

    def c(color_256: int, fallback: int) -> int:
        return color_256 if has_256 else fallback

    def safe_pair(pair_id: int, fg: int, bg: int) -> None:
        try:
            curses.init_pair(pair_id, fg, bg)
        except curses.error:
            pass

    default_bg = -1

    safe_pair(TITLE, c(201, curses.COLOR_MAGENTA), default_bg)          # kräftiges Magenta
    safe_pair(SUBTITLE, c(219, curses.COLOR_WHITE), default_bg)          # zartes Rosa
    safe_pair(MENU_NORMAL, c(225, curses.COLOR_WHITE), default_bg)       # pastell rosa/weiß
    safe_pair(MENU_SELECTED, c(233, curses.COLOR_BLACK), c(213, curses.COLOR_MAGENTA))  # dunkel auf pink
    safe_pair(MENU_DISABLED, c(245, curses.COLOR_WHITE), default_bg)     # grau
    safe_pair(COUNTER, c(218, curses.COLOR_MAGENTA), default_bg)         # rosa
    safe_pair(JOINT_PAPER, c(224, curses.COLOR_WHITE), default_bg)       # cremig-rosa Papier
    safe_pair(JOINT_ASH, c(238, curses.COLOR_BLACK), default_bg)         # dunkelgrau Asche
    safe_pair(JOINT_CHERRY_HOT, c(208, curses.COLOR_RED), default_bg)    # orange Glut
    safe_pair(JOINT_CHERRY_COOL, c(197, curses.COLOR_RED), default_bg)   # pink-rote Glut
    safe_pair(JOINT_FILTER, c(223, curses.COLOR_YELLOW), default_bg)     # beige Filter
    safe_pair(SMOKE, c(189, curses.COLOR_WHITE), default_bg)             # zarter Lavendel-Rauch
    safe_pair(ASH_FLAKES, c(240, curses.COLOR_WHITE), default_bg)        # graue Ascheflocken
    safe_pair(BORDER, c(213, curses.COLOR_MAGENTA), default_bg)          # pink Rahmen
    safe_pair(SUCCESS, c(156, curses.COLOR_GREEN), default_bg)           # pastellgrün
    safe_pair(INFO, c(159, curses.COLOR_CYAN), default_bg)               # pastellcyan
    safe_pair(TIMER_TEXT, c(201, curses.COLOR_MAGENTA), default_bg)      # magenta
    safe_pair(PASTEL_YELLOW, c(229, curses.COLOR_YELLOW), default_bg)    # pastellgelb
