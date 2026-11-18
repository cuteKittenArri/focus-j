"""
Große Ziffern aus Blockzeichen für den Timer (frei von curses, testbar).

Grundlage ist eine 3x5-Pixel-Schrift. Zwei Darstellungen:

    "large"  5 Zeilen, jedes Pixel = "██"          (für normale Terminals)
    "small"  3 Zeilen, Halbblöcke ▀ ▄ █            (für niedrige Terminals)

In beiden Fällen sind die Pixel optisch quadratisch.
"""

from typing import Dict, List, Tuple

_GLYPHS: Dict[str, List[str]] = {
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"],
    "3": ["###", "..#", ".##", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", "..#", "..#", "..#"],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "###"],
    ":": [".", "#", ".", "#", "."],
    "+": ["...", ".#.", "###", ".#.", "..."],
    " ": [".", ".", ".", ".", "."],
}

_HALF = {
    (True, True): "█",
    (True, False): "▀",
    (False, True): "▄",
    (False, False): " ",
}


def _pixels(text: str) -> List[str]:
    """Pixelzeilen ('#'/'.') für den Text, Zeichen durch 1 Pixel Abstand getrennt."""
    rows = [""] * 5
    for i, ch in enumerate(text):
        glyph = _GLYPHS.get(ch, _GLYPHS[" "])
        for r in range(5):
            rows[r] += ("." if i else "") + glyph[r]
    return rows


def render_big(text: str, style: str = "large") -> List[str]:
    """Text als Liste von Zeilen in Blockzeichen. style: 'large' | 'small' | 'plain'."""
    if style == "plain":
        return [text]
    px = _pixels(text)
    if style == "large":
        return ["".join("██" if p == "#" else "  " for p in row) for row in px]
    px.append("." * len(px[0]))
    return [
        "".join(_HALF[(a == "#", b == "#")] for a, b in zip(px[r], px[r + 1]))
        for r in range(0, 6, 2)
    ]


def big_size(text: str, style: str = "large") -> Tuple[int, int]:
    """(Breite, Höhe) des gerenderten Texts in Terminalzellen."""
    lines = render_big(text, style)
    return max(len(line) for line in lines), len(lines)
