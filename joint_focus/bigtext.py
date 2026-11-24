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
    rows = [""] * 5
    for i, ch in enumerate(text):
        glyph = _GLYPHS.get(ch, _GLYPHS[" "])
        for r in range(5):
            rows[r] += ("." if i else "") + glyph[r]
    return rows


def render_big(text: str, style: str = "large") -> List[str]:
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
    lines = render_big(text, style)
    return max(len(line) for line in lines), len(lines)
