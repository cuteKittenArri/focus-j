# 🚬 Joint Focus

A terminal focus-timer. Instead of a boring progress bar, a joint slowly
burns down. Every **fully completed** session earns you a joint, which
you collect in the top-right corner and can redeem later.

<p align="center">
  <img src="https://arri-eta.vercel.app/focus-j-menu.png" alt="Main menu with focus durations and stats" width="49%">
  <img src="https://arri-eta.vercel.app/focus-j-timer.png" alt="Running focus session with the burning joint" width="49%">
</p>

## Requirements

- Python 3.8+ (standard library only, including `curses`; no pip packages)
- A 256-color terminal. Terminals that can redefine colors (Kitty, xterm, …) show the
  exact palette; others use the closest 256 colors, and 8-color terminals fall back to
  basic colors.

## Running

```bash
python3 main.py
```

To make it available everywhere:

```bash
chmod +x main.py
ln -s "$(pwd)/main.py" ~/.local/bin/joint-focus   # ~/.local/bin must be in your PATH
joint-focus
```

## Controls

| Screen       | Keys                                                                 |
|--------------|----------------------------------------------------------------------|
| Main menu    | `↑`/`↓` or `j`/`k` navigate · `Enter` select · `q` quit              |
| Custom time  | `↑`/`↓` ±5 min · `←`/`→` or `h`/`l` ±1 min · `0`–`9` type minutes · `Backspace` delete · `Enter` start · `Esc`/`q` back |
| Focus session| `p` pause/resume · `q` abort (no joint awarded)                      |
| Session done | any key returns to the menu                                          |

Custom time allows 1–360 minutes and remembers your last choice.

## Saved data

Your joint stash and stats (completed sessions, focused minutes, redeemed joints) persist in
`~/.local/share/joint-focus/state.json` (or `$XDG_DATA_HOME/joint-focus/state.json`).

## Project structure

```
main.py                 # entry point
joint_focus/
├── colors.py           # color roles (curses)
├── ascii_joint.py      # joint, ash and smoke rendering
├── bigtext.py          # large block digits for the timer
├── storage.py          # JSON persistence
└── ui.py               # curses UI: menu, timer, redeeming
```

## Customizing

- **Durations**: `DURATIONS` in `joint_focus/ui.py` (`"key": (seconds, "Label")`).
  Custom-time limits: `CUSTOM_MIN`, `CUSTOM_MAX`, `CUSTOM_STEP`.
- **Colors**: `joint_focus/colors.py`. The palette is four hex colors
  ([colorhunt](https://colorhunt.co/palette/2900445000718a2a78eee3b0)); every other shade is
  mixed from them, so swapping those four constants gives you a new palette.
- **Joint look**: `joint_focus/ascii_joint.py` — `PAPER_LEN`, `FILTER_LEN`, `TIP_HEIGHT`,
  `ASH_BREAK_MIN`/`ASH_BREAK_MAX`, smoke in `_smoke`. The length adapts to terminal width.
