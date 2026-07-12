# 🌿 Joint Focus

Ein Terminal-Fokus-Timer für Linux/zsh. Statt eines langweiligen Fortschrittsbalkens
brennt während deiner Fokuszeit ein Joint langsam ab. Für jede **komplett** durchgehaltene
Session wird ein Joint "freigespielt" - diese sammelst du oben rechts und kannst sie
später einlösen.

## Voraussetzungen

- Python 3.8+
- `curses` (ist bei Linux/macOS Standard in Python enthalten, keine Installation nötig)
- Ein Terminal mit 256-Farben-Unterstützung für die vollen Pastell-/Magenta-Töne
  (praktisch jedes moderne Terminal, z.B. Standard-zsh-Terminal, iTerm, Alacritty, Kitty ...).
  Ohne 256 Farben fällt die App automatisch auf Standardfarben zurück.

Keine externen pip-Pakete nötig - reine Python-Standardbibliothek.

## Start

```bash
cd joint-focus
python3 main.py
```

Oder ausführbar machen und direkt starten:

```bash
chmod +x main.py
./main.py
```

### Optional: global verfügbar machen

```bash
mkdir -p ~/.local/bin
ln -s "$(pwd)/main.py" ~/.local/bin/joint-focus
# ~/.local/bin muss in deinem PATH sein (meist schon der Fall)
```

Danach einfach von überall:

```bash
joint-focus
```

## Bedienung

**Hauptmenü**
- `↑`/`↓` oder `j`/`k`: navigieren
- `Enter`: Auswahl bestätigen
- `q`: beenden

**Während der Fokuszeit**
- `p`: Pause / Weiter
- `q`: Session abbrechen (kein Joint wird vergeben)

**Nach abgeschlossener Session**
- Beliebige Taste: zurück zum Menü

## Wie der Joint funktioniert

- Die Glut wandert von links (frisch) nach rechts (Filter) - je mehr Zeit vergeht,
  desto mehr ist verbrannt.
- Asche und Rauch sind rein optisch, haben aber keinen Einfluss auf die Zeitmessung.
- Bei Erreichen des Filters ist die Session komplett durchgelaufen → **+1 Joint**.

## Speicherung

Dein Joint-Vorrat und deine Statistiken (abgeschlossene Sessions, fokussierte Minuten,
eingelöste Joints) werden dauerhaft gespeichert unter:

```
~/.local/share/joint-focus/state.json
```

(oder unter `$XDG_DATA_HOME/joint-focus/state.json`, falls gesetzt). Die Datei bleibt
über Neustarts der App erhalten - kein Datenverlust beim Beenden.

## Projektstruktur

```
joint-focus/
├── main.py                  # Einstiegspunkt
├── README.md
└── joint_focus/
    ├── __init__.py
    ├── colors.py             # Magenta/Rosa/Pastell-Farbpaletten (curses)
    ├── ascii_joint.py         # Reine Rendering-Logik für die Joint-Animation
    ├── storage.py            # Persistenz (JSON-Datei) für den Joint-Counter
    └── ui.py                 # Curses-Vollbild-UI: Menü, Timer, Einlösen
```

## Anpassen

- **Neue Zeitlängen**: `DURATIONS`-Dict in `joint_focus/ui.py` erweitern
  (Format: `"key": (sekunden, "Anzeigename")`).
- **Farben ändern**: `joint_focus/colors.py` - dort sind alle 256er-Farbcodes
  (und Fallback-Farben) an einer Stelle gesammelt.
- **Joint-Länge/-Aussehen**: `joint_focus/ascii_joint.py` (`INNER_LEN`, Zeichen
  für Papier/Asche/Glut/Filter).
