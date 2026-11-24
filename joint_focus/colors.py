import curses
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

# --- Palette -----------------------------------------------------------------
NIGHT = "#290044"
VIOLET = "#500071"
PLUM = "#8A2A78"
CREAM = "#EEE3B0"

BACKGROUND = NIGHT


def _rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    return "#%02X%02X%02X" % tuple(
        round(x + (y - x) * t) for x, y in zip(_rgb(a), _rgb(b)))


# --- Derived shades ------------------------------------------------------------
CREAM_HI = mix(CREAM, "#FFFFFF", 0.5)
BLUSH = mix(PLUM, CREAM, 0.72)
ROSE = mix(PLUM, CREAM, 0.50)
MAUVE = mix(VIOLET, CREAM, 0.48)
FAINT = mix(VIOLET, CREAM, 0.24)
GLOW = mix(PLUM, "#FF4FE0", 0.55)

_D = -1

_BLACK = curses.COLOR_BLACK
_RED = curses.COLOR_RED
_YELLOW = curses.COLOR_YELLOW
_MAGENTA = curses.COLOR_MAGENTA
_WHITE = curses.COLOR_WHITE

Role = Tuple[str, Optional[str], int, int]


def _r(fg: str, fg8: int, bg: Optional[str] = None, bg8: int = _D) -> Role:
    return (fg, bg, fg8, bg8)


def _ramp(a: str, b: str, steps: Sequence[float]) -> List[str]:
    return [mix(a, b, t) for t in steps]


_rule = _ramp(NIGHT, PLUM, (0.14, 0.24, 0.34, 0.44, 0.54, 0.64))
_digits = _ramp(CREAM, PLUM, (0.0, 0.18, 0.38, 0.58, 0.78))
_plus1 = [CREAM_HI] + _ramp(CREAM, PLUM, (0.0, 0.18, 0.36, 0.54))
_smoke = _ramp(VIOLET, CREAM, (0.78, 0.56, 0.36, 0.18))

ROLES: Dict[str, Role] = {
    "bg":            _r(CREAM, _WHITE),

    # --- Header & frame ------------------------------------------------
    "title":         _r(CREAM, _WHITE),
    "title_spark":   _r(ROSE, _MAGENTA),
    "subtitle":      _r(MAUVE, _MAGENTA),
    "pill":          _r(CREAM, _WHITE, PLUM, _MAGENTA),
    "pill_cap":      _r(PLUM, _MAGENTA),
    **{f"rule_{i}": _r(c, _MAGENTA) for i, c in enumerate(_rule)},

    # --- Menu ------------------------------------------------------------
    "card_border":   _r(PLUM, _MAGENTA),
    "card_title":    _r(ROSE, _MAGENTA),
    "item":          _r(CREAM, _WHITE),
    "item_detail":   _r(ROSE, _MAGENTA),
    "item_disabled": _r(FAINT, _BLACK),
    "sel":           _r(CREAM, _WHITE, PLUM, _MAGENTA),
    "sel_cap":       _r(PLUM, _MAGENTA),
    "stat_value":    _r(CREAM_HI, _WHITE),
    "stat_label":    _r(MAUVE, _MAGENTA),

    # --- General text -------------------------------------------------------
    "key":           _r(ROSE, _MAGENTA),
    "hint":          _r(MAUVE, _WHITE),
    "sep":           _r(FAINT, _MAGENTA),
    "muted":         _r(MAUVE, _WHITE),
    "info":          _r(BLUSH, _WHITE),
    "success":       _r(BLUSH, _WHITE),

    # --- Timer digits (gradient cream -> plum) --------------------------------
    **{f"digit_{i}": _r(c, _WHITE if i < 2 else _MAGENTA) for i, c in enumerate(_digits)},
    "digit_paused":  _r(mix(VIOLET, PLUM, 0.35), _MAGENTA),

    # --- "+1" after a completed session (gradient highlight -> cream -> rose) ---
    **{f"gold_{i}": _r(c, _WHITE if i < 3 else _MAGENTA) for i, c in enumerate(_plus1)},

    # --- Joint ---------------------------------------------------------------
    "paper_top":     _r(CREAM_HI, _WHITE),
    "paper":         _r(CREAM, _WHITE),
    "paper_lo":      _r(mix(CREAM, PLUM, 0.20), _WHITE),
    "paper_shadow":  _r(mix(CREAM, PLUM, 0.45), _MAGENTA),
    "filter_a":      _r(mix(PLUM, CREAM, 0.28), _MAGENTA),
    "filter_b":      _r(PLUM, _MAGENTA),
    "filter_lo_a":   _r(mix(PLUM, VIOLET, 0.25), _MAGENTA),
    "filter_lo_b":   _r(mix(PLUM, VIOLET, 0.55), _MAGENTA),
    "filter_shadow": _r(VIOLET, _MAGENTA),
    "ash_hi_0":      _r(mix(NIGHT, CREAM, 0.66), _WHITE),
    "ash_lo_0":      _r(mix(NIGHT, CREAM, 0.52), _WHITE),
    "ash_hi_1":      _r(mix(NIGHT, CREAM, 0.58), _WHITE),
    "ash_lo_1":      _r(mix(NIGHT, CREAM, 0.44), _BLACK),
    "ash_hi_2":      _r(mix(NIGHT, CREAM, 0.48), _BLACK),
    "ash_lo_2":      _r(mix(NIGHT, CREAM, 0.34), _BLACK),
    "ash_shadow":    _r(mix(NIGHT, CREAM, 0.18), _BLACK),
    "ash_warm_hi":   _r(mix(GLOW, CREAM, 0.30), _MAGENTA),
    "ash_warm_lo":   _r(PLUM, _MAGENTA),
    "char":          _r(mix(PLUM, NIGHT, 0.30), _MAGENTA),
    "char_lo":       _r(VIOLET, _MAGENTA),
    "cherry_0":      _r(PLUM, _RED),
    "cherry_1":      _r(GLOW, _MAGENTA),
    "cherry_2":      _r(mix(GLOW, CREAM, 0.35), _MAGENTA),
    "cherry_3":      _r(mix(GLOW, CREAM, 0.65), _YELLOW),
    "cherry_top":    _r(GLOW, _MAGENTA),
    "ember":         _r(mix(PLUM, NIGHT, 0.25), _RED),
    "flake":         _r(mix(NIGHT, CREAM, 0.38), _BLACK),
    **{f"smoke_{i}": _r(c, _WHITE if i < 2 else _BLACK) for i, c in enumerate(_smoke)},
}

RULE: List[str] = [f"rule_{i}" for i in range(6)]
DIGITS: List[str] = [f"digit_{i}" for i in range(5)]
GOLD: List[str] = [f"gold_{i}" for i in range(5)]

_attrs: Dict[str, int] = {}


# ---------------------------------------------------------------------------
# Hex -> terminal color number
# ---------------------------------------------------------------------------

def _xterm_rgb(index: int) -> Tuple[int, int, int]:
    if index >= 232:
        v = 8 + 10 * (index - 232)
        return v, v, v
    steps = (0, 95, 135, 175, 215, 255)
    n = index - 16
    return steps[n // 36], steps[(n // 6) % 6], steps[n % 6]


def _distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    rm = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return (2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db


def _ranked_256(hex_color: str) -> List[int]:
    rgb = _rgb(hex_color)
    return sorted(range(16, 256), key=lambda i: _distance(_xterm_rgb(i), rgb))


def _can_redefine() -> bool:
    try:
        return curses.can_change_color() and bool(curses.tigetstr("oc"))
    except curses.error:
        return False


def _assign_slots(hexes: Sequence[str], redefine: bool) -> Dict[str, int]:
    slots: Dict[str, int] = {}
    used = set()
    for h in dict.fromkeys(hexes):
        ranked = _ranked_256(h)
        index = next((i for i in ranked if i not in used), ranked[0]) if redefine else ranked[0]
        used.add(index)
        slots[h] = index
        if redefine:
            r, g, b = (-(-v * 1000 // 255) for v in _rgb(h))
            try:
                curses.init_color(index, r, g, b)
            except curses.error:
                pass
    return slots


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_colors(win=None) -> None:
    _attrs.clear()
    if not curses.has_colors():
        return
    curses.start_color()
    default_bg = _D
    try:
        curses.use_default_colors()
    except curses.error:
        default_bg = _BLACK

    has_256 = curses.COLORS >= 256
    if has_256:
        hexes = [BACKGROUND] + [c for fg, bg, _, _ in ROLES.values() for c in (fg, bg) if c]
        slots = _assign_slots(hexes, _can_redefine())

    for pair_id, (name, (fg, bg, fg8, bg8)) in enumerate(ROLES.items(), start=1):
        if pair_id >= curses.COLOR_PAIRS:
            break
        if has_256:
            f, b = slots[fg], slots[bg or BACKGROUND]
        else:
            f, b = fg8, (default_bg if bg8 == _D else bg8)
        try:
            curses.init_pair(pair_id, f, b)
            _attrs[name] = curses.color_pair(pair_id)
        except curses.error:
            pass

    if win is not None and "bg" in _attrs:
        win.bkgd(" ", _attrs["bg"])


def attr(name: str) -> int:
    return _attrs.get(name, 0)


# ---------------------------------------------------------------------------
# Terminal background (border/padding)
# ---------------------------------------------------------------------------

def _osc(payload: str) -> None:
    if not sys.stdout.isatty() or os.environ.get("TERM", "") in ("linux", "dumb"):
        return
    sys.stdout.write(f"\033]{payload}\a")
    sys.stdout.flush()


def set_terminal_background() -> None:
    r, g, b = _rgb(BACKGROUND)
    _osc(f"11;rgb:{r:02x}/{g:02x}/{b:02x}")


def reset_terminal_background() -> None:
    _osc("111")
