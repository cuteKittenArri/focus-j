"""
Erzeugt die Frames für den langsam abbrennenden Joint.

Diese Funktionen sind bewusst frei von curses-Aufrufen gehalten, damit sie
sich isoliert testen lassen. joint_focus.ui übernimmt das eigentliche Zeichnen.

Der Joint wird als abgerundete Röhre über drei Zeilen dargestellt
(Oberkante / Inhalt / Unterkante), damit er wie ein echter Joint aussieht
und nicht wie eine einzelne Strichlinie:

      ╭────────────────────────────────╮
     (▓▓▓▓▓▓▓▓●▬▬▬▬╱▬▬▬▬▬▬▬▬▬▬▬▬▒░▒░▒░▒)
      ╰────────────────────────────────╯

    [Asche][Glut][Papier mit Naht][Filter]

Je größer der Fortschritt (0.0 -> 1.0), desto mehr Asche und desto kürzer
das verbleibende Papier - die Glut "wandert" von links Richtung Filter.
Die Gesamtbreite bleibt dabei IMMER konstant (auch fertig durchgebrannt),
damit die Röhre nicht "springt".
"""

from dataclasses import dataclass
from typing import List, Tuple

PAPER_LEN = 28          # Länge des brennbaren Papierteils in Zeichen
FILTER_LEN = 7          # Länge des Filters/Mundstücks in Zeichen

ASH_CHAR = "▓"
PAPER_CHAR = "█"
SEAM_CHAR = "█"          # angedeutete Naht des Rollpapiers
FILTER_PATTERN = "▒░"    # gewelltes Muster für die Filter-Textur
CHERRY_HOT = "█"
CHERRY_COOL = "░"

BORDER_LEFT_CAP = "|"
BORDER_RIGHT_CAP = "|"

SMOKE_FRAMES = [
    "        ",
    "        ",
    "        ",
    "        ",
    "        ",
    "        ",
]

TAG_ASH = "ash"
TAG_CHERRY = "cherry"
TAG_PAPER = "paper"
TAG_FILTER = "filter"


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _paper_run(length: int) -> str:
    """Papierstück mit einer angedeuteten Rollpapier-Naht in der Mitte."""
    if length <= 0:
        return ""
    if length >= 4:
        mid = length // 2
        chars = [PAPER_CHAR] * length
        chars[mid] = SEAM_CHAR
        return "".join(chars)
    return PAPER_CHAR * length


def _filter_run(length: int) -> str:
    """Gewelltes Filtermuster (Pappfilter-Optik)."""
    return "".join(FILTER_PATTERN[i % len(FILTER_PATTERN)] for i in range(length))


@dataclass
class JointFrame:
    top_border: str
    bottom_border: str
    body_segments: List[Tuple[str, str]]
    left_cap: str
    right_cap: str
    smoke: str
    ash_flakes: str
    cherry_offset: int
    burnt_len: int
    finished: bool
    inner_width: int


def render_joint(progress: float, tick: int) -> JointFrame:
    """Berechnet einen einzelnen Animationsframe für den gegebenen Fortschritt (0..1)."""
    progress = clamp(progress, 0.0, 1.0)

    burnt = int(round(PAPER_LEN * progress))
    burnt = int(clamp(burnt, 0, PAPER_LEN))
    finished = burnt >= PAPER_LEN

    body_segments: List[Tuple[str, str]] = []
    cherry_offset = burnt

    if burnt > 0:
        body_segments.append((ASH_CHAR * burnt, TAG_ASH))

    if not finished:
        cherry_char = CHERRY_HOT if tick % 2 == 0 else CHERRY_COOL
        body_segments.append((cherry_char, TAG_CHERRY))
        remaining_paper = PAPER_LEN - burnt - 1
    else:
        remaining_paper = 0

    if remaining_paper > 0:
        body_segments.append((_paper_run(remaining_paper), TAG_PAPER))

    body_segments.append((_filter_run(FILTER_LEN), TAG_FILTER))

    inner_width = PAPER_LEN + FILTER_LEN
    top_border = "╭" + "─" * inner_width + "╮"
    bottom_border = "╰" + "─" * inner_width + "╯"

    smoke = SMOKE_FRAMES[tick % len(SMOKE_FRAMES)] if not finished else ""

    if burnt > 0:
        flake_chars = []
        for i in range(burnt):
            seed = (i * 7 + tick) % 5
            flake_chars.append("." if seed == 0 else ("," if seed == 2 else " "))
        ash_flakes = "".join(flake_chars)
    else:
        ash_flakes = ""

    return JointFrame(
        top_border=top_border,
        bottom_border=bottom_border,
        body_segments=body_segments,
        left_cap=BORDER_LEFT_CAP,
        right_cap=BORDER_RIGHT_CAP,
        smoke=smoke,
        ash_flakes=ash_flakes,
        cherry_offset=cherry_offset,
        burnt_len=burnt,
        finished=finished,
        inner_width=inner_width,
    )


def total_width() -> int:
    """Gesamtbreite der Joint-Darstellung in Zeichen (für Zentrierung), inkl. Kappen."""
    return PAPER_LEN + FILTER_LEN + 2
