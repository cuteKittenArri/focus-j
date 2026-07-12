"""
Die eigentliche Vollbild-TUI von Joint Focus (curses-basiert).
"""

import curses
import time
from typing import Dict, List, Optional, Tuple

from . import colors
from .ascii_joint import render_joint, total_width
from .storage import add_joint, load_state, redeem_joint

# (Sekunden, Anzeigename)
DURATIONS: Dict[str, Tuple[int, str]] = {
    "30": (30 * 60, "30 Minuten"),
    "60": (60 * 60, "1 Stunde"),
    "120": (120 * 60, "2 Stunden"),
}

TICK_MS = 250  # Animations-/Eingabe-Takt in Millisekunden


def safe_addstr(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """addstr, das nie wegen zu kleinem Fenster abstürzt."""
    try:
        max_y, max_x = win.getmaxyx()
        if y < 0 or y >= max_y or x >= max_x:
            return
        available = max_x - x
        if available <= 0:
            return
        win.addstr(y, x, text[:available], attr)
    except curses.error:
        pass


def center_x(win, text_len: int) -> int:
    _, max_x = win.getmaxyx()
    return max(0, (max_x - text_len) // 2)


def draw_header(win, state: Dict) -> None:
    max_y, max_x = win.getmaxyx()
    title = "~ F O C U S ~"
    subtitle = "u have to get shit done"
    safe_addstr(win, 1, center_x(win, len(title)), title,
                curses.color_pair(colors.TITLE) | curses.A_BOLD)
    safe_addstr(win, 2, center_x(win, len(subtitle)), subtitle,
                curses.color_pair(colors.SUBTITLE))

    counter_text = f" Joints: {state['joints']} "
    safe_addstr(win, 1, max(0, max_x - len(counter_text) - 2), counter_text,
                curses.color_pair(colors.COUNTER) | curses.A_BOLD | curses.A_REVERSE)

    line = "─" * max(0, max_x - 2)
    safe_addstr(win, 3, 1, line, curses.color_pair(colors.BORDER))


def draw_footer(win, hints: str) -> None:
    max_y, max_x = win.getmaxyx()
    safe_addstr(win, max_y - 2, 1, "─" * max(0, max_x - 2),
                curses.color_pair(colors.BORDER))
    safe_addstr(win, max_y - 1, center_x(win, len(hints)), hints,
                curses.color_pair(colors.INFO))


def draw_joint(win, y: int, progress: float, tick: int) -> None:
    """
    Zeichnet die brennende Joint-Animation zentriert um Zeile y (kein Rahmen,
    nur die reine Röhren-Füllung). Layout von oben nach unten:

        y-1   Rauch
        y     Inhalt   (ash●paper|filter)
        y+1   Ascheflocken
    """
    frame = render_joint(progress, tick)
    width = frame.inner_width
    x = center_x(win, width)

    if frame.smoke:
        smoke_x = center_x(win, len(frame.smoke))
        safe_addstr(win, y - 1, smoke_x, frame.smoke, curses.color_pair(colors.SMOKE))

    # Inhalt: Segmente nacheinander zeichnen (kein Rahmen, keine Kappen)
    cur_x = x
    for text, tag in frame.body_segments:
        if tag == "cherry":
            color = colors.JOINT_CHERRY_HOT if tick % 2 == 0 else colors.JOINT_CHERRY_COOL
            attr = curses.color_pair(color) | curses.A_BOLD
        elif tag == "ash":
            attr = curses.color_pair(colors.JOINT_ASH)
        elif tag == "paper":
            attr = curses.color_pair(colors.JOINT_PAPER) | curses.A_BOLD
        elif tag == "filter":
            attr = curses.color_pair(colors.JOINT_FILTER) | curses.A_BOLD
        else:
            attr = 0
        safe_addstr(win, y, cur_x, text, attr)
        cur_x += len(text)

    # Ascheflocken-Zeile unter dem Joint, an der Position der Asche ausgerichtet
    if frame.ash_flakes:
        safe_addstr(win, y + 1, x, frame.ash_flakes, curses.color_pair(colors.ASH_FLAKES))


def format_time(seconds: int) -> str:
    seconds = max(0, seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class MenuItem:
    def __init__(self, key: str, label: str, enabled: bool = True):
        self.key = key
        self.label = label
        self.enabled = enabled


def menu_screen(stdscr, state: Dict) -> str:
    """Zeigt das Hauptmenü, gibt den gewählten Action-Key zurück."""
    items = [
        MenuItem("30", "30 Minuten Fokus"),
        MenuItem("60", "1 Stunde Fokus"),
        MenuItem("120", "2 Stunden Fokus"),
        MenuItem("redeem", f"Joint einlösen (Vorrat: {state['joints']})", state["joints"] > 0),
        MenuItem("quit", "Beenden"),
    ]
    selected = 0
    stdscr.timeout(-1)  # blockierend im Menü, kein unnötiges CPU-Spinnen

    while True:
        stdscr.erase()
        max_y, max_x = stdscr.getmaxyx()
        draw_header(stdscr, state)

        start_y = 6
        for i, item in enumerate(items):
            is_selected = i == selected
            label = f"  {item.label}  "
            x = center_x(stdscr, len(label))
            if not item.enabled:
                attr = curses.color_pair(colors.MENU_DISABLED)
            elif is_selected:
                attr = curses.color_pair(colors.MENU_SELECTED) | curses.A_BOLD
            else:
                attr = curses.color_pair(colors.MENU_NORMAL)
            prefix = "> " if is_selected else "  "
            safe_addstr(stdscr, start_y + i * 2, max(0, x - 2), prefix, attr)
            safe_addstr(stdscr, start_y + i * 2, x, label, attr)

        stats = (f"Sessions abgeschlossen: {state['sessions_completed']}   "
                 f"Fokus-Minuten gesamt: {state['minutes_focused']}   "
                 f"Eingelöst: {state['joints_redeemed']}")
        safe_addstr(stdscr, start_y + len(items) * 2 + 1, center_x(stdscr, len(stats)),
                    stats, curses.color_pair(colors.SUBTITLE))

        draw_footer(stdscr, "↑/↓ oder j/k: navigieren   Enter: auswählen   q: beenden")
        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            selected = (selected - 1) % len(items)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected = (selected + 1) % len(items)
        elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
            item = items[selected]
            if item.enabled:
                return item.key
        elif key in (ord('q'), ord('Q')):
            return "quit"


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
        progress = elapsed_active / duration_seconds if duration_seconds else 1.0

        stdscr.erase()
        draw_header(stdscr, state)

        max_y, max_x = stdscr.getmaxyx()

        heading = f"Fokus-Session: {label}"
        safe_addstr(stdscr, 5, center_x(stdscr, len(heading)), heading,
                    curses.color_pair(colors.TIMER_TEXT) | curses.A_BOLD)

        time_text = format_time(int(round(max(0, remaining))))
        if paused:
            time_text += "  (PAUSE)"
        safe_addstr(stdscr, 7, center_x(stdscr, len(time_text)), time_text,
                    curses.color_pair(colors.TIMER_TEXT) | curses.A_BOLD)

        joint_y = max_y // 2
        draw_joint(stdscr, joint_y, progress, tick)

        percent_text = f"{int(min(100, progress * 100))}% verraucht"
        safe_addstr(stdscr, joint_y + 3, center_x(stdscr, len(percent_text)), percent_text,
                    curses.color_pair(colors.SUBTITLE))

        draw_footer(stdscr, "p: Pause/Weiter   q: abbrechen (kein Joint)")
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


def finished_screen(stdscr, state: Dict, label: str) -> None:
    stdscr.timeout(-1)
    tick = 0
    stdscr.nodelay(True)
    stdscr.timeout(200)
    start = time.monotonic()

    while True:
        stdscr.erase()
        draw_header(stdscr, state)
        max_y, max_x = stdscr.getmaxyx()

        msg = f"Fertig! {label} durchgehalten."
        safe_addstr(stdscr, 5, center_x(stdscr, len(msg)), msg,
                    curses.color_pair(colors.SUCCESS) | curses.A_BOLD)

        reward = "+1 Joint freigespielt!"
        safe_addstr(stdscr, 7, center_x(stdscr, len(reward)), reward,
                    curses.color_pair(colors.COUNTER) | curses.A_BOLD)

        # fertig durchgebrannter Joint (progress = 1.0), leichtes Glimmen im Wechsel
        joint_y = max_y // 2
        draw_joint(stdscr, joint_y, 1.0, tick)

        sparkle_chars = "✦ ✧ ✺ ✩"
        sparkle = " ".join(sparkle_chars.split()[i % 4] for i in range(3))
        safe_addstr(stdscr, joint_y + 3, center_x(stdscr, len(sparkle)), sparkle,
                    curses.color_pair(colors.PASTEL_YELLOW))

        total_text = f"Joints im Vorrat: {state['joints']}"
        safe_addstr(stdscr, joint_y + 5, center_x(stdscr, len(total_text)), total_text,
                    curses.color_pair(colors.COUNTER))

        draw_footer(stdscr, "Beliebige Taste: zurück zum Menü")
        stdscr.refresh()

        key = stdscr.getch()
        if key != -1:
            break
        tick += 1

    stdscr.nodelay(False)


def redeem_screen(stdscr, state: Dict) -> None:
    stdscr.timeout(-1)
    success = redeem_joint(state)

    stdscr.erase()
    draw_header(stdscr, state)
    max_y, max_x = stdscr.getmaxyx()

    if success:
        msg = "Ein Joint wurde eingelöst. enjoy! 🍁"
        color = colors.SUCCESS
    else:
        msg = "Keine Joints im Vorrat - erst eine Fokus-Session abschließen!"
        color = colors.MENU_DISABLED

    safe_addstr(stdscr, max_y // 2, center_x(stdscr, len(msg)), msg,
                curses.color_pair(color) | curses.A_BOLD)

    total_text = f"Joints im Vorrat: {state['joints']}"
    safe_addstr(stdscr, max_y // 2 + 2, center_x(stdscr, len(total_text)), total_text,
                curses.color_pair(colors.COUNTER))

    draw_footer(stdscr, "Beliebige Taste: zurück zum Menü")
    stdscr.refresh()
    stdscr.getch()


def run(stdscr) -> None:
    curses.curs_set(0)
    colors.init_colors()
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
