"""
Die eigentliche Vollbild-TUI von Joint Focus (curses-basiert).

Screens: Hauptmenü, laufende Fokus-Session, "Geschafft!", Joint eingelöst.

    Farben          -> joint_focus.colors
    Joint-Animation -> joint_focus.ascii_joint
    große Ziffern   -> joint_focus.bigtext
"""

import curses
import math
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from . import colors
from .ascii_joint import JOINT_HEIGHT, dimensions, noise, render_joint
from .bigtext import big_size, render_big
from .storage import add_joint, load_state, redeem_joint

A = colors.attr

# (Sekunden, Anzeigename)
DURATIONS: Dict[str, Tuple[int, str]] = {
    "30": (30 * 60, "30 Minuten"),
    "60": (60 * 60, "1 Stunde"),
    "120": (120 * 60, "2 Stunden"),
}

TICK_MS = 250            # Animations-/Eingabe-Takt in Millisekunden
MIN_W, MIN_H = 44, 16    # darunter wird nur ein Hinweis angezeigt
HEADER_ROWS = 4          # Rand, Titel, Untertitel, Linie
FOOTER_ROWS = 3          # Abstand, Linie, Tastenhinweise
CARD_W = 42              # Breite der Menükarte
MAX_SMOKE = 7            # maximale Rauchhöhe in Zeilen

BOLD = curses.A_BOLD
ITALIC = getattr(curses, "A_ITALIC", 0)

SPARKLE = " ·✧✦✧·  "     # Funkel-Animation, ein Zeichen pro Tick

Run = Tuple[str, int]    # (Text, curses-Attribut)


# ---------------------------------------------------------------------------
# Zeichen-Helfer
# ---------------------------------------------------------------------------

def text_width(text: str) -> int:
    """Anzeigebreite in Terminalzellen (Emoji & Co. zählen doppelt)."""
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def put(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """addstr, das nie wegen zu kleinem Fenster abstürzt."""
    max_y, max_x = win.getmaxyx()
    if not text or y < 0 or y >= max_y or x >= max_x:
        return
    if x < 0:
        text, x = text[-x:], 0
    try:
        win.addstr(y, x, text[: max_x - x], attr)
    except curses.error:
        pass  # z.B. Schreiben in die allerletzte Zelle unten rechts


def put_runs(win, y: int, x: int, runs: Sequence[Run]) -> None:
    for text, attr in runs:
        put(win, y, x, text, attr)
        x += text_width(text)


def runs_width(runs: Sequence[Run]) -> int:
    return sum(text_width(text) for text, _ in runs)


def center_x(win, width: int) -> int:
    _, max_x = win.getmaxyx()
    return max(0, (max_x - width) // 2)


def put_center(win, y: int, text: str, attr: int = 0) -> None:
    put(win, y, center_x(win, text_width(text)), text, attr)


def put_runs_center(win, y: int, runs: Sequence[Run]) -> None:
    put_runs(win, y, center_x(win, runs_width(runs)), runs)


def content_area(win) -> Tuple[int, int]:
    """(erste Zeile, Anzahl Zeilen) des Bereichs zwischen Kopf und Fuß."""
    max_y, _ = win.getmaxyx()
    return HEADER_ROWS, max(0, max_y - HEADER_ROWS - FOOTER_ROWS)


def format_time(seconds: int) -> str:
    seconds = max(0, seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_minutes(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60}h {minutes % 60:02d}m"


# ---------------------------------------------------------------------------
# Bausteine: Kopf, Fuß, Linien, Pillen, Karten
# ---------------------------------------------------------------------------

def draw_rule(win, y: int) -> None:
    """Horizontale Linie, die zu den Rändern hin sanft ausblendet."""
    _, max_x = win.getmaxyx()
    width = max(0, max_x - 4)
    shades = colors.RULE
    for i in range(width):
        edge = min(i, width - 1 - i)
        put(win, y, 2 + i, "─", A(shades[min(edge // 2, len(shades) - 1)]))


def pill_width(text: str) -> int:
    return text_width(text) + 2


def draw_pill(win, y: int, x: int, text: str) -> None:
    """Text als abgerundete goldene Pille:  ▐ text ▌"""
    put(win, y, x, "▐", A("pill_cap"))
    put(win, y, x + 1, text, A("pill") | BOLD)
    put(win, y, x + 1 + text_width(text), "▌", A("pill_cap"))


def draw_header(win, state: Dict) -> None:
    _, max_x = win.getmaxyx()
    put_runs_center(win, 1, [
        ("✦", A("title_spark")),
        ("   F O C U S   ", A("title") | BOLD),
        ("✦", A("title_spark")),
    ])
    put_center(win, 2, "u have to get shit done", A("subtitle") | ITALIC)

    n = state["joints"]
    counter = f" ✿ {n} " if max_x < 72 else f" ✿ {n} {'Joint' if n == 1 else 'Joints'} "
    draw_pill(win, 1, max_x - 2 - pill_width(counter), counter)

    draw_rule(win, 3)


def draw_footer(win, hints: Sequence[Tuple[str, str]]) -> None:
    """Tastenhinweise: Taste in Gold, Beschreibung gedimmt."""
    max_y, _ = win.getmaxyx()
    draw_rule(win, max_y - 2)
    runs: List[Run] = []
    for i, (key, desc) in enumerate(hints):
        if i:
            runs.append(("   ·   ", A("sep")))
        runs.append((key, A("key") | BOLD))
        runs.append((" " + desc, A("hint")))
    put_runs_center(win, max_y - 1, runs)


def draw_card(win, y: int, x: int, height: int, width: int, title: str = "") -> None:
    """Abgerundete Karte mit optionalem Titel in der Oberkante."""
    border = A("card_border")
    put(win, y, x, "╭" + "─" * (width - 2) + "╮", border)
    for row in range(y + 1, y + height - 1):
        put(win, row, x, "│", border)
        put(win, row, x + width - 1, "│", border)
    put(win, y + height - 1, x, "╰" + "─" * (width - 2) + "╯", border)
    if title:
        put(win, y, x + 2, f" {title} ", A("card_title") | BOLD)


def draw_card_divider(win, y: int, x: int, width: int) -> None:
    put(win, y, x, "├" + "╌" * (width - 2) + "┤", A("card_border"))


def draw_too_small(win, extra: str = "") -> bool:
    """Zeigt einen Hinweis, falls das Terminal zu klein ist. True = zu klein."""
    max_y, max_x = win.getmaxyx()
    if max_y >= MIN_H and max_x >= MIN_W:
        return False
    mid = max_y // 2
    put_center(win, mid - 1, "✿  Terminal zu klein", A("title") | BOLD)
    put_center(win, mid + 1, f"mind. {MIN_W}×{MIN_H} · aktuell {max_x}×{max_y}", A("muted"))
    if extra:
        put_center(win, mid + 2, extra, A("info"))
    return True


def draw_big(win, y: int, text: str, style: str, shades: Sequence[str], attr_extra: int = 0) -> None:
    """Großer Text, Zeile für Zeile mit eigenem Farbton (Verlauf)."""
    lines = render_big(text, style)
    x = center_x(win, max(len(line) for line in lines))
    for i, line in enumerate(lines):
        shade = shades[min(len(shades) - 1, i * len(shades) // len(lines))]
        put(win, y + i, x, line, A(shade) | attr_extra)


def draw_joint(win, top_y: int, progress: float, tick: int,
               smoke_height: int, lit: bool = True) -> None:
    """Zeichnet den Joint (JOINT_HEIGHT Zeilen ab top_y) plus Rauch darüber."""
    _, max_x = win.getmaxyx()
    paper_len, filter_len = dimensions(max_x)
    frame = render_joint(progress, tick, paper_len, filter_len, smoke_height, lit)
    x0 = center_x(win, frame.width)

    for p in frame.smoke:
        put(win, top_y + p.row, x0 + p.col, p.char, A(p.tag))
    for r, row in enumerate(frame.rows):
        for c, (char, tag) in enumerate(row):
            if tag:
                put(win, top_y + r, x0 + c, char, A(tag))


def draw_sparkles(win, y0: int, x0: int, height: int, width: int,
                  tick: int, count: int = 28) -> None:
    """Funkelnde Sternchen rund um ein Rechteck (das Rechteck selbst bleibt frei)."""
    tags = ("title_spark", "title", "stat_value")
    for i in range(count):
        px = x0 - 12 + int(noise(i, 1) * (width + 24))
        py = y0 - 1 + int(noise(i, 2) * (height + 2))
        if x0 - 2 <= px <= x0 + width + 1 and y0 <= py < y0 + height:
            continue
        char = SPARKLE[(tick + int(noise(i, 3) * len(SPARKLE))) % len(SPARKLE)]
        if char != " ":
            put(win, py, px, char, A(tags[i % len(tags)]))


# ---------------------------------------------------------------------------
# Hauptmenü
# ---------------------------------------------------------------------------

class MenuItem:
    def __init__(self, key: str, label: str, detail: str = "", enabled: bool = True):
        self.key = key
        self.label = label
        self.detail = detail
        self.enabled = enabled


def draw_menu_item(win, y: int, card_x: int, card_w: int, item: MenuItem, selected: bool) -> None:
    x = card_x + 2
    inner = card_w - 4
    label_x = x + 4
    detail_x = x + inner - 3 - text_width(item.detail)

    if selected:
        bar = A("sel") | BOLD
        put(win, y, x, "▐", A("sel_cap"))
        put(win, y, x + 1, " " * (inner - 2), bar)
        put(win, y, x + inner - 1, "▌", A("sel_cap"))
        put(win, y, x + 2, "▸", bar)
        put(win, y, label_x, item.label, bar)
        put(win, y, detail_x, item.detail, bar)
    else:
        enabled = item.enabled
        put(win, y, label_x, item.label, A("item") if enabled else A("item_disabled"))
        put(win, y, detail_x, item.detail, A("item_detail") if enabled else A("item_disabled"))


def draw_stats(win, y: int, state: Dict) -> None:
    stats = [
        (str(state["sessions_completed"]), "Sessions"),
        (format_minutes(state["minutes_focused"]), "Fokuszeit"),
        (str(state["joints_redeemed"]), "eingelöst"),
    ]
    col_w = 14
    x0 = center_x(win, col_w * len(stats))
    for i, (value, label) in enumerate(stats):
        mid = x0 + i * col_w + col_w // 2
        put(win, y, mid - text_width(value) // 2, value, A("stat_value") | BOLD)
        put(win, y + 1, mid - text_width(label) // 2, label, A("stat_label"))
        if i:
            put(win, y, x0 + i * col_w, "│", A("sep"))
            put(win, y + 1, x0 + i * col_w, "│", A("sep"))


def draw_menu(win, state: Dict, focus: List[MenuItem], other: List[MenuItem], selected_key: str) -> None:
    _, max_x = win.getmaxyx()
    top, avail = content_area(win)

    card_w = min(CARD_W, max_x - 4)
    pad = 1 if avail >= 15 else 0
    card_h = 3 + len(focus) + len(other) + pad * 4
    show_stats = avail >= card_h + 3
    total = card_h + (3 if show_stats else 0)

    y = top + max(0, (avail - total) // 2)
    x = center_x(win, card_w)
    draw_card(win, y, x, card_h, card_w, "✦ Fokus-Session")

    row = y + 1 + pad
    for item in focus:
        draw_menu_item(win, row, x, card_w, item, item.key == selected_key)
        row += 1
    row += pad
    draw_card_divider(win, row, x, card_w)
    row += 1 + pad
    for item in other:
        draw_menu_item(win, row, x, card_w, item, item.key == selected_key)
        row += 1

    if show_stats:
        draw_stats(win, y + card_h + 1, state)


def menu_screen(stdscr, state: Dict) -> str:
    """Zeigt das Hauptmenü, gibt den gewählten Action-Key zurück."""
    focus = [
        MenuItem("30", "30 Minuten", "◔"),
        MenuItem("60", "1 Stunde", "◑"),
        MenuItem("120", "2 Stunden", "●"),
    ]
    other = [
        MenuItem("redeem", "Joint einlösen", f"{state['joints']} ✿", state["joints"] > 0),
        MenuItem("quit", "Beenden", "q"),
    ]
    items = focus + other
    selectable = [item for item in items if item.enabled]
    selected = 0
    stdscr.timeout(-1)  # blockierend im Menü, kein unnötiges CPU-Spinnen

    while True:
        stdscr.erase()
        if not draw_too_small(stdscr):
            draw_header(stdscr, state)
            draw_menu(stdscr, state, focus, other, selectable[selected].key)
            draw_footer(stdscr, [("↑↓", "navigieren"), ("⏎", "auswählen"), ("q", "beenden")])
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            selected = (selected - 1) % len(selectable)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected = (selected + 1) % len(selectable)
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            return selectable[selected].key
        elif key in (ord('q'), ord('Q')):
            return "quit"


# ---------------------------------------------------------------------------
# Fokus-Session
# ---------------------------------------------------------------------------

def draw_timer(win, label: str, duration: int, elapsed: float, paused: bool, tick: int) -> None:
    _, max_x = win.getmaxyx()
    top, avail = content_area(win)

    remaining = max(0.0, duration - elapsed)
    progress = elapsed / duration if duration else 1.0
    time_text = format_time(int(math.ceil(remaining)))

    # Überschrift, Abstand, Info-Zeile, Joint, Prozent-Zeile
    fixed = 3 + JOINT_HEIGHT + 1
    style = "plain"
    for candidate in ("large", "small"):
        width, height = big_size(time_text, candidate)
        if width <= max_x - 4 and fixed + height + 3 <= avail:
            style = candidate
            break
    digits_h = big_size(time_text, style)[1]
    smoke_h = int(max(0, min(MAX_SMOKE, avail - fixed - digits_h)))
    # übrigen Platz bei großen Terminals als Luft zwischen die Blöcke verteilen
    gap = int(max(0, min(2, (avail - fixed - digits_h - smoke_h) // 4)))
    total = fixed + digits_h + smoke_h + 3 * gap
    y = top + max(0, (avail - total) // 2)

    # Überschrift mit blinkendem "Aufnahme"-Punkt
    if paused:
        dot = A("digit_paused")
    else:
        dot = A("title") if (tick // 4) % 2 == 0 else A("sep")
    put_runs_center(win, y, [
        ("●", dot),
        ("  Fokus-Session", A("muted")),
        ("  ·  ", A("sep")),
        (label, A("item") | BOLD),
    ])

    # große Restzeit
    digits_y = y + 2 + gap
    shades = ["digit_paused"] if paused else colors.DIGITS
    draw_big(win, digits_y, time_text, style, shades, BOLD if style == "plain" else 0)

    # Info: Endzeit bzw. Pause
    info_y = digits_y + digits_h
    if paused:
        text = " ❚❚ PAUSIERT "
        draw_pill(win, info_y, center_x(win, pill_width(text)), text)
    else:
        end = datetime.now() + timedelta(seconds=remaining)
        put_runs_center(win, info_y, [
            ("endet um ", A("muted")),
            (end.strftime("%H:%M"), A("info") | BOLD),
        ])

    # Joint + Rauch
    joint_y = info_y + 1 + gap + smoke_h
    draw_joint(win, joint_y, progress, tick, smoke_h, lit=not paused)

    percent = int(min(100, progress * 100))
    put_runs_center(win, joint_y + JOINT_HEIGHT + gap, [
        (f"{percent} %", A("stat_value") | BOLD),
        (" verraucht", A("muted")),
        ("   ·   ", A("sep")),
        (format_time(int(elapsed)), A("item")),
        (" / " + format_time(duration), A("muted")),
    ])


def timer_screen(stdscr, state: Dict, duration_seconds: int, label: str) -> bool:
    """
    Läuft die Fokus-Zeit herunter und zeichnet den abbrennenden Joint.
    Gibt True zurück, wenn die Zeit vollständig durchgelaufen ist,
    False, wenn abgebrochen wurde.
    """
    stdscr.timeout(TICK_MS)

    start = time.monotonic()
    paused = False
    pause_started_at: Optional[float] = None
    paused_total = 0.0
    tick = 0

    while True:
        now = time.monotonic()
        if paused:
            elapsed_active = (pause_started_at - start) - paused_total
        else:
            elapsed_active = (now - start) - paused_total
        remaining = duration_seconds - elapsed_active

        stdscr.erase()
        if not draw_too_small(stdscr, f"Timer läuft weiter: {format_time(int(math.ceil(max(0, remaining))))}"):
            draw_header(stdscr, state)
            draw_timer(stdscr, label, duration_seconds, elapsed_active, paused, tick)
            hints = [("p", "weiter" if paused else "Pause"), ("q", "abbrechen (kein Joint)")]
            draw_footer(stdscr, hints)
        stdscr.refresh()

        if remaining <= 0:
            return True

        key = stdscr.getch()
        if not paused:
            tick += 1

        if key in (ord('q'), ord('Q')):
            return False
        elif key in (ord('p'), ord('P')):
            if paused:
                # Weiter: angesammelte Pausenzeit verbuchen
                paused_total += now - pause_started_at
                paused = False
                pause_started_at = None
            else:
                paused = True
                pause_started_at = now


# ---------------------------------------------------------------------------
# Session geschafft
# ---------------------------------------------------------------------------

def draw_finished(win, state: Dict, label: str, tick: int) -> None:
    top, avail = content_area(win)

    style = "large" if avail >= 14 + 2 else "small"
    big_w, big_h = big_size("+1", style)
    # Funkelrand, "+1", Funkelrand, Nachricht, Vorrat, Abstand, Joint
    total = 1 + big_h + 1 + 2 + 1 + JOINT_HEIGHT
    y = top + max(0, (avail - total) // 2)

    big_y = y + 1
    big_x = center_x(win, big_w)
    draw_sparkles(win, big_y, big_x, big_h, big_w, tick)
    draw_big(win, big_y, "+1", style, colors.GOLD)

    msg_y = big_y + big_h + 1
    put_runs_center(win, msg_y, [
        ("Geschafft!", A("success") | BOLD),
        (f"  {label} durchgehalten.", A("item")),
    ])
    put_runs_center(win, msg_y + 1, [
        ("Joint freigespielt", A("stat_value")),
        ("  ·  ", A("sep")),
        (f"Vorrat: {state['joints']}", A("muted")),
    ])

    draw_joint(win, msg_y + 3, 1.0, tick, 0, lit=False)


def wait_for_key(stdscr) -> int:
    """Nächste echte Taste (Fenstergrößen-Änderungen zählen nicht), -1 = Timeout."""
    key = stdscr.getch()
    return -1 if key == curses.KEY_RESIZE else key


def finished_screen(stdscr, state: Dict, label: str) -> None:
    stdscr.timeout(TICK_MS)
    tick = 0
    while True:
        stdscr.erase()
        if not draw_too_small(stdscr):
            draw_header(stdscr, state)
            draw_finished(stdscr, state, label, tick)
            draw_footer(stdscr, [("beliebige Taste", "zurück zum Menü")])
        stdscr.refresh()

        if wait_for_key(stdscr) != -1:
            break
        tick += 1


# ---------------------------------------------------------------------------
# Joint einlösen
# ---------------------------------------------------------------------------

def draw_redeem(win, state: Dict, success: bool, tick: int) -> None:
    top, avail = content_area(win)

    if not success:
        mid = top + avail // 2
        put_center(win, mid - 1, "Keine Joints im Vorrat", A("item_disabled") | BOLD)
        put_center(win, mid + 1, "erst eine Fokus-Session abschließen!", A("muted"))
        return

    fixed = JOINT_HEIGHT + 2  # Joint (inkl. Flockenzeile als Abstand), Nachricht, Vorrat
    smoke_h = int(max(0, min(MAX_SMOKE, avail - fixed)))
    y = top + max(0, (avail - fixed - smoke_h) // 2)

    joint_y = y + smoke_h
    draw_joint(win, joint_y, 0.04, tick, smoke_h, lit=True)

    msg_y = joint_y + JOINT_HEIGHT
    put_runs_center(win, msg_y, [
        ("✿ ", A("success")),
        ("Joint eingelöst", A("success") | BOLD),
        (" - enjoy!", A("item")),
    ])
    rest = state["joints"]
    put_center(win, msg_y + 1, f"noch {rest} im Vorrat" if rest else "Vorrat leer - Zeit für die nächste Session",
               A("muted"))


def redeem_screen(stdscr, state: Dict) -> None:
    success = redeem_joint(state)
    stdscr.timeout(TICK_MS)
    tick = 0
    while True:
        stdscr.erase()
        if not draw_too_small(stdscr):
            draw_header(stdscr, state)
            draw_redeem(stdscr, state, success, tick)
            draw_footer(stdscr, [("beliebige Taste", "zurück zum Menü")])
        stdscr.refresh()

        if wait_for_key(stdscr) != -1:
            break
        tick += 1


# ---------------------------------------------------------------------------
# Einstieg
# ---------------------------------------------------------------------------

def run(stdscr) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    colors.init_colors(stdscr)
    stdscr.keypad(True)

    state = load_state()

    while True:
        action = menu_screen(stdscr, state)

        if action == "quit":
            break
        elif action == "redeem":
            redeem_screen(stdscr, state)
        elif action in DURATIONS:
            seconds, label = DURATIONS[action]
            completed = timer_screen(stdscr, state, seconds, label)
            if completed:
                add_joint(state, seconds // 60)
                finished_screen(stdscr, state, label)
