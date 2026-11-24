import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

PAPER_LEN = 36
FILTER_LEN = 8
MIN_TOTAL_LEN = 26

TIP_HEIGHT = 6
LOWER_BLOCKS = " ▁▂▃▄▅▆▇█"
FULL = "█"
SHADOW = "▀"

JOINT_HEIGHT = 5

ASH_BREAK_MIN = 5
ASH_BREAK_MAX = 9
HEAP_BLOCKS = "▁▁▂▂▃"
FALL_GRAVITY = 0.7
FALL_TILT = 1.6
FALL_FLOOR = 4
LAND_FRAME = 3
FALL_FRAMES = 7

Cell = Tuple[str, str]
EMPTY: Cell = (" ", "")


@dataclass
class SmokeParticle:
    row: int
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
class AshFall:
    start: int
    end: int
    age: int


@dataclass
class _ColumnStyle:
    top: str
    hi: str
    lo: str
    shadow: str
    hi_char: str = FULL
    lo_char: str = FULL


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def noise(a: int, b: int) -> float:
    n = (a * 374761393 + b * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 0x100000000


def dimensions(max_width: int) -> Tuple[int, int]:
    total = int(clamp(max_width * 0.58, MIN_TOTAL_LEN, PAPER_LEN + FILTER_LEN))
    filter_len = max(5, round(total / 5.5))
    return total - filter_len, filter_len


def top_height(col: int, paper_len: int) -> int:
    if col >= paper_len:
        return 0
    return int(round(TIP_HEIGHT * (1 - col / paper_len)))


def burnt_columns(progress: float, paper_len: int) -> int:
    progress = clamp(progress, 0.0, 1.0)
    return int(clamp(math.floor(progress * paper_len + 1e-9), 0, paper_len))


def ash_attached_from(burnt: int) -> int:
    start, k = 0, 0
    span = ASH_BREAK_MAX - ASH_BREAK_MIN + 1
    while True:
        length = ASH_BREAK_MIN + int(noise(k, 41) * span)
        if burnt < start + length:
            return start
        stub = 1 if noise(k, 43) < 0.7 else 2
        start += length - stub
        k += 1


class AshTracker:
    def __init__(self) -> None:
        self._paper_len: Optional[int] = None
        self._attached = 0
        self._fall: Optional[Tuple[int, int, int]] = None

    def update(self, progress: float, paper_len: int, frame: int) -> Optional[AshFall]:
        attached = ash_attached_from(burnt_columns(progress, paper_len))
        if paper_len != self._paper_len:
            self._paper_len, self._attached, self._fall = paper_len, attached, None
        elif attached > self._attached:
            self._fall = (self._attached, attached, frame)
            self._attached = attached
        elif attached < self._attached:
            self._attached, self._fall = attached, None

        if self._fall is not None:
            start, end, since = self._fall
            age = frame - since
            if age < FALL_FRAMES:
                return AshFall(start, end, age)
            self._fall = None
        return None


def _column_style(kind: str, col: int, burnt: int, tick: int, lit: bool) -> _ColumnStyle:
    if kind == "filter":
        dark = col % 3 == 0
        return _ColumnStyle("", "filter_b" if dark else "filter_a",
                            "filter_lo_b" if dark else "filter_lo_a", "filter_shadow")

    if kind == "ash":
        age = burnt - col
        if lit and age == 1:
            return _ColumnStyle("ash_warm_hi", "ash_warm_hi", "ash_warm_lo", "ash_shadow")
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

        if r >= 1 and noise(r, tick // 2 + 17) < 0.4:
            side = 1 if noise(r, tick // 2 + 3) < 0.5 else -1
            dx = side * (1 + int(noise(r, tick // 2 + 9) * 2))
            fade = f"smoke_{min(3, int(q * 3.6) + 1)}"
            particles.append(SmokeParticle(origin_row - r, col + dx, "·", fade))
    return particles


def _heap_cell(col: int) -> Cell:
    char = HEAP_BLOCKS[int(noise(col, 19) * len(HEAP_BLOCKS))]
    return char, "ash_lo_1" if noise(col, 23) < 0.6 else "ash_lo_2"


def _put_if_empty(rows: List[List[Cell]], row: int, col: int, cell: Cell) -> None:
    if 0 <= col < len(rows[row]) and not rows[row][col][1]:
        rows[row][col] = cell


def _draw_fall(rows: List[List[Cell]], fall: AshFall, paper_len: int, burnt: int, tick: int) -> None:
    span = max(1, fall.end - fall.start)
    a = fall.age
    for col in range(fall.start, fall.end):
        bucket = 1 if noise(col, 5) < 0.6 else 2
        hi, lo = f"ash_hi_{bucket}", f"ash_lo_{bucket}"

        if a == 0:
            style = _column_style("ash", col, burnt, tick, lit=False)
            h = top_height(col, paper_len)
            if h > 0:
                rows[0][col] = (LOWER_BLOCKS[h], style.top)
            rows[1][col] = (FULL, style.hi)
            rows[2][col] = (FULL, style.lo)
            rows[3][col] = (SHADOW, style.shadow)
        elif a <= LAND_FRAME:
            tip = (fall.end - col) / span
            drop = FALL_GRAVITY * a * a + FALL_TILT * tip * min(a, 2)
            top = 2 + min(FALL_FLOOR, int(round(drop)))
            bottom = top + 4
            for r in range(JOINT_HEIGHT):
                upper = top <= 2 * r < bottom
                lower = top <= 2 * r + 1 < bottom
                if upper or lower:
                    char = FULL if upper and lower else ("▀" if upper else "▄")
                    rows[r][col] = (char, lo if 2 * r + 2 >= bottom else hi)
        elif a == LAND_FRAME + 1:
            rows[4][col] = ("▆" if noise(col, 29) < 0.6 else "▅", lo)
        elif a == LAND_FRAME + 2:
            rows[4][col] = ("▄" if noise(col, 31) < 0.6 else "▃", lo)
        else:
            rows[4][col] = _heap_cell(col)

    if a in (LAND_FRAME + 1, LAND_FRAME + 2):
        spread = a - LAND_FRAME
        _put_if_empty(rows, 4, fall.start - spread, ("·", "flake"))
        _put_if_empty(rows, 3, fall.start - spread - 1, ("˙", "flake"))
        _put_if_empty(rows, 3, fall.end - 1 + spread, ("·", "flake"))


def render_joint(progress: float, tick: int,
                 paper_len: int = PAPER_LEN, filter_len: int = FILTER_LEN,
                 smoke_height: int = 4, lit: bool = True,
                 fall: Optional[AshFall] = None) -> JointFrame:
    width = paper_len + filter_len
    burnt = burnt_columns(progress, paper_len)
    finished = burnt >= paper_len
    cherry = None if finished else burnt
    attached = ash_attached_from(burnt)
    falling = range(fall.start, fall.end) if fall else range(0)

    rows: List[List[Cell]] = [[EMPTY] * width for _ in range(JOINT_HEIGHT)]

    for col in range(width):
        if col >= paper_len:
            kind = "filter"
        elif col < attached:
            kind = "gone"
        elif col < burnt:
            kind = "ash"
        elif col == cherry:
            kind = "cherry"
        elif col == burnt + 1:
            kind = "char"
        else:
            kind = "paper"

        if kind == "gone":
            if col not in falling:
                rows[4][col] = _heap_cell(col)
            continue

        style = _column_style(kind, col, burnt, tick, lit)
        if kind == "ash" and col == attached and attached > 0:
            style.top = ""
            style.hi_char = "▐"
            style.lo_char = "▐" if noise(col, 13) < 0.5 else FULL

        h = top_height(col, paper_len)
        if h > 0 and style.top:
            rows[0][col] = (LOWER_BLOCKS[h], style.top)
        rows[1][col] = (style.hi_char, style.hi)
        rows[2][col] = (style.lo_char, style.lo)
        rows[3][col] = (SHADOW, style.shadow)

        if kind == "ash" and noise(col, tick // 3) < 0.08:
            rows[4][col] = ("·" if noise(col, 11) < 0.6 else ".", "flake")

    if fall is not None:
        _draw_fall(rows, fall, paper_len, burnt, tick)

    smoke: List[SmokeParticle] = []
    if lit and cherry is not None:
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
