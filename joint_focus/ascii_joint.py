"""
Erzeugt die Frames für den langsam abbrennenden Joint.

Diese Funktionen sind bewusst frei von curses-Aufrufen gehalten, damit sie
sich isoliert testen lassen. joint_focus.ui übernimmt das eigentliche Zeichnen.

Der Joint ist eine leicht konische Röhre - vorne an der Glut dicker, hinten
zum Filter hin schmaler. Die Verjüngung entsteht durch Achtel-Blockzeichen
in der obersten Zeile, die zwei Körperzeilen sind wie ein Zylinder schattiert
(oben hell, unten dunkler):

                 )
                ╱
               (
      ▆▆▆▆▆▆▅▅▅▅▅▅▄▄▄▄▄▄▃▃▃▃▃▃▂▂▂▂▂▂▁▁▁▁▁
      ███████████████████████████████████████████████
      ███████████████████████████████████████████████
      ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
       ·   .
      [Asche][Glut][Papier ......................][Filter]

    Zeile 0  Oberkante (Verjüngung)
    Zeile 1  Körper oben (Glanz)
    Zeile 2  Körper unten
    Zeile 3  Schattenkante
    Zeile 4  herabfallende Ascheflocken

Darüber steigt animierter Rauch aus der Glut auf (eigene Liste, Zeilen < 0).

Je größer der Fortschritt (0.0 -> 1.0), desto mehr Asche - die Glut "wandert"
von links Richtung Filter. Die Gesamtbreite bleibt dabei IMMER konstant,
damit die Röhre nicht "springt".
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

PAPER_LEN = 36          # Standardlänge des brennbaren Papierteils in Zeichen
FILTER_LEN = 8          # Standardlänge des Filters/Mundstücks in Zeichen
MIN_TOTAL_LEN = 26      # kleinste Gesamtlänge (schmale Terminals)

TIP_HEIGHT = 6          # Höhe der Oberkante an der Spitze, in Achteln einer Zeile
LOWER_BLOCKS = " ▁▂▃▄▅▆▇█"
FULL = "█"
SHADOW = "▀"

JOINT_HEIGHT = 5        # Oberkante, Körper oben, Körper unten, Schatten, Flocken

Cell = Tuple[str, str]  # (Zeichen, Farbrolle) - leere Rolle = nichts zeichnen
EMPTY: Cell = (" ", "")


@dataclass
class SmokeParticle:
    row: int    # relativ zu Joint-Zeile 0, negativ = darüber
    col: int
    char: str
    tag: str


@dataclass
class JointFrame:
    rows: List[List[Cell]]
    smoke: List[SmokeParticle]
    width: int
    cherry_col: Optional[int]
    burnt_len: int
    finished: bool


@dataclass
class _ColumnStyle:
    top: str            # Rolle der Oberkante ("" = nicht zeichnen)
    hi: str             # Rolle Körper oben
    lo: str             # Rolle Körper unten
    shadow: str         # Rolle Schattenkante
    hi_char: str = FULL
    lo_char: str = FULL


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def noise(a: int, b: int) -> float:
    """Deterministisches Pseudo-Rauschen in [0, 1) - gleiche Eingabe, gleiches Ergebnis."""
    n = (a * 374761393 + b * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 0x100000000


def dimensions(max_width: int) -> Tuple[int, int]:
    """Papier- und Filterlänge passend zur Terminalbreite."""
    total = int(clamp(max_width * 0.58, MIN_TOTAL_LEN, PAPER_LEN + FILTER_LEN))
    filter_len = max(5, round(total / 5.5))
    return total - filter_len, filter_len


def top_height(col: int, paper_len: int) -> int:
    """Höhe der Oberkante (in Achteln) an Spalte col - verjüngt sich zum Filter."""
    if col >= paper_len:
        return 0
    return int(round(TIP_HEIGHT * (1 - col / paper_len)))


def _column_style(kind: str, col: int, burnt: int, tick: int, lit: bool) -> _ColumnStyle:
    if kind == "filter":
        dark = col % 3 == 0          # feine Streifen wie gerollte Pappe
        return _ColumnStyle("", "filter_b" if dark else "filter_a",
                            "filter_lo_b" if dark else "filter_lo_a", "filter_shadow")

    if kind == "ash":
        age = burnt - col            # 1 = direkt an der Glut
        if lit and age == 1:
            return _ColumnStyle("ash_warm_hi", "ash_warm_hi", "ash_warm_lo", "ash_shadow")
        # frische Asche ist hell, ältere etwas dunkler - plus leichte Melierung
        bucket = 0 if age <= 3 else (1 if age <= 9 else 2)
        hi_bucket = min(2, bucket + 1) if noise(col, 5) < 0.25 else bucket
        lo_bucket = min(2, bucket + 1) if noise(col, 6) < 0.25 else bucket
        hi = f"ash_hi_{hi_bucket}"
        return _ColumnStyle(hi, hi, f"ash_lo_{lo_bucket}", "ash_shadow")

    if kind == "cherry":
        if not lit:
            return _ColumnStyle("ember", "ember", "ember", "ember")
        glow = (1, 2, 3, 2, 1, 0)[tick % 6]
        return _ColumnStyle("cherry_top", f"cherry_{glow}", f"cherry_{max(0, glow - 1)}", "ember")

    if kind == "char":
        return _ColumnStyle("char", "char", "char_lo", "ash_shadow")

    return _ColumnStyle("paper_top", "paper", "paper_lo", "paper_shadow")


def _smoke(origin_row: int, origin_col: int, tick: int, height: int) -> List[SmokeParticle]:
    """
    Zustandsloser Rauch: eine wellige Rauchfahne, deren Welle mit jedem Tick
    nach oben wandert. Unten zusammenhängend ( ╱ ) ╲, oben zerfasert in
    Pünktchen, dazu blasst die Farbe nach oben hin aus.
    """
    particles: List[SmokeParticle] = []
    if height <= 0:
        return particles
    t = tick * 0.55
    for r in range(height):
        q = r / max(1, height - 1)
        phi = r * 0.8 - t
        amp = 0.35 + r * 0.38
        s = math.sin(phi)
        col = origin_col + int(round(s * amp + r * 0.45))
        tag = f"smoke_{min(3, int(q * 3.6))}"

        if q <= 0.7:
            if s < -0.6:
                char = "("
            elif s > 0.6:
                char = ")"
            else:
                slope = math.cos(phi) * 0.8 * amp + 0.45
                char = "╱" if slope > 0 else "╲"
        else:
            char = "·" if noise(r, tick // 2) < 0.5 else "∙"
        particles.append(SmokeParticle(origin_row - r, col, char, tag))

        # vereinzelte Rauchpünktchen neben der Fahne
        if r >= 1 and noise(r, tick // 2 + 17) < 0.4:
            side = 1 if noise(r, tick // 2 + 3) < 0.5 else -1
            dx = side * (1 + int(noise(r, tick // 2 + 9) * 2))
            fade = f"smoke_{min(3, int(q * 3.6) + 1)}"
            particles.append(SmokeParticle(origin_row - r, col + dx, "·", fade))
    return particles


def render_joint(progress: float, tick: int,
                 paper_len: int = PAPER_LEN, filter_len: int = FILTER_LEN,
                 smoke_height: int = 4, lit: bool = True) -> JointFrame:
    """
    Berechnet einen einzelnen Animationsframe für den gegebenen Fortschritt (0..1).

    lit=False zeigt eine gedimmte Glut ohne Rauch (z.B. während einer Pause).
    """
    progress = clamp(progress, 0.0, 1.0)
    width = paper_len + filter_len

    burnt = int(clamp(math.floor(progress * paper_len + 1e-9), 0, paper_len))
    finished = burnt >= paper_len
    cherry = None if finished else burnt

    rows: List[List[Cell]] = [[EMPTY] * width for _ in range(JOINT_HEIGHT)]

    for col in range(width):
        if col >= paper_len:
            kind = "filter"
        elif col < burnt:
            kind = "ash"
        elif col == cherry:
            kind = "cherry"
        elif col == burnt + 1:
            kind = "char"            # verkohlter Rand direkt hinter der Glut
        else:
            kind = "paper"

        style = _column_style(kind, col, burnt, tick, lit)
        h = top_height(col, paper_len)
        if h > 0 and style.top:
            rows[0][col] = (LOWER_BLOCKS[h], style.top)
        rows[1][col] = (style.hi_char, style.hi)
        rows[2][col] = (style.lo_char, style.lo)
        rows[3][col] = (SHADOW, style.shadow)

        # herabrieselnde Ascheflocken unter dem verbrannten Teil
        if kind == "ash" and noise(col, tick // 3) < 0.08:
            rows[4][col] = ("·" if noise(col, 11) < 0.6 else ".", "flake")

    smoke: List[SmokeParticle] = []
    if lit and cherry is not None:
        # gelegentlich fällt ein kleiner Funke von der Glut
        if noise(tick // 2, 99) < 0.18:
            rows[4][cherry] = ("·", "cherry_2")
        origin_row = -1 if top_height(cherry, paper_len) > 0 else 0
        smoke = _smoke(origin_row, cherry, tick, smoke_height)

    return JointFrame(
        rows=rows,
        smoke=smoke,
        width=width,
        cherry_col=cherry,
        burnt_len=burnt,
        finished=finished,
    )
