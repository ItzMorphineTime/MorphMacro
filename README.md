# AutoClick

A configurable Python autoclicker with both a basic desktop GUI and a CLI hotkey mode.
The repo also includes a standalone macro recorder app.

## Features

- Structured GUI layout with grouped settings panels
- Global hotkeys in GUI mode for toggle and quit
- Configurable toggle/quit hotkeys in both GUI and CLI modes
- High-visibility active feedback (status banner, window title, live metrics)
- Optional `Always on top` mode to keep the GUI visible while clicking in other windows
- Optional CLI mode with global hotkeys
- Configurable click interval with optional random jitter
- Left, right, or middle button support
- Optional double-click mode
- Optional click-count limit and/or duration limit
- Current-cursor mode or fixed-position mode
- Built-in failsafe: move mouse to `(0, 0)` to pause clicking
- JSON config support with CLI overrides

## Requirements

- Python 3.8+
- `pynput`
- Tkinter (usually included with standard Python installs)

## Installation

```bash
git clone <your-repo-url>
cd AutoClick
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
# macOS/Linux
# source .venv/bin/activate
pip install pynput
```

## Quick Start

Run GUI mode (default):

```bash
python AutoClicker.py
```

GUI default hotkeys:

- Toggle clicking: `<f8>`
- Quit app: `<esc>`

Run CLI hotkey mode:

```bash
python AutoClicker.py --cli
```

CLI default hotkeys:

- Toggle clicking: `<f8>`
- Quit app: `<esc>`

Run macro recorder:

```bash
python Macros.py
```

## GUI Overview

The GUI includes controls for:

- Status banner with clear `ACTIVE`/`PAUSED` state
- Live metrics: click count, elapsed time, and CPS
- Interval and jitter
- Button selection (`left`, `right`, `middle`)
- Double-click toggle
- Click-count and duration limits
- Fixed-position mode with `x` and `y`
- Failsafe toggle
- Always-on-top window mode
- Toggle and quit hotkeys (pynput format, for example `<f8>` or `<ctrl>+<alt>+q`)

Buttons:

- `Apply Settings`: rebuilds the worker using current form values and rebinds global hotkeys
- `Start / Pause`: toggles clicking with color/state feedback and hotkey label
- `Quit`: stops the worker and closes the app

## Macro Recorder (`Macros.py`)

`Macros.py` is a separate GUI tool for recording and replaying macros.

Main capabilities:

- Records keyboard actions, mouse clicks, and mouse scroll events
- Optional mouse movement recording
- Live action list showing every recorded step with timestamp
- Clear feedback for `IDLE` / `RECORDING` / `PLAYING`
- Save and load macros as JSON
- Optional always-on-top mode
- Global hotkeys for record/play start and stop
- Hotkeys are configurable in the GUI (`Macro Hotkeys` section + `Apply Hotkeys`)

Default macro hotkeys:

- Start recording: `F9`
- Stop recording: `F10`
- Start playback: `F11`
- Stop playback: `F12`

You can change these in the `Macro Hotkeys` panel (for example to `<ctrl>+<alt>+r`) and click `Apply Hotkeys`.

Typical workflow:

1. Launch `python Macros.py`
2. Click `Start Recording`
3. Perform your actions in any window
4. Click `Stop Recording`
5. Review the action list and click `Play Macro` (or save to JSON)

## CLI Usage

```bash
python AutoClicker.py --cli [options]
```

### Common examples

```bash
# Faster clicks (20 CPS)
python AutoClicker.py --cli --interval 0.05

# Add jitter for less-uniform timing
python AutoClicker.py --cli --interval 0.08 --jitter 0.02

# Right-button double click
python AutoClicker.py --cli --button right --double

# Stop after 500 clicks
python AutoClicker.py --cli --count 500

# Run for 30 seconds
python AutoClicker.py --cli --duration 30

# Click at fixed screen position
python AutoClicker.py --cli --fixed --x 960 --y 540

# Custom hotkeys (CLI mode)
python AutoClicker.py --cli --toggle-key "<f6>" --quit-key "<ctrl>+<alt>+q"

# Disable corner failsafe
python AutoClicker.py --cli --no-failsafe
```

### Options

- `--gui`: Explicitly run GUI mode (default)
- `--cli`: Run CLI hotkey mode
- `--config <path>`: Load JSON config file (keys map to `ClickConfig` fields)
- `--interval <float>`: Seconds between clicks
- `--jitter <float>`: Random jitter added as `+/- jitter`
- `--button <left|right|middle>`: Mouse button
- `--double`: Double-click each cycle
- `--count <int>`: Number of clicks (`0` = unlimited)
- `--duration <float>`: Duration in seconds (`0` = unlimited)
- `--fixed`: Enable fixed-position mode
- `--x <int>`: Fixed X coordinate (used with `--fixed`)
- `--y <int>`: Fixed Y coordinate (used with `--fixed`)
- `--no-failsafe`: Disable `(0, 0)` corner failsafe
- `--always-on-top`: Start GUI in always-on-top mode
- `--toggle-key <hotkey>`: Toggle hotkey in `pynput` format (CLI mode)
- `--quit-key <hotkey>`: Quit hotkey in `pynput` format (CLI mode)

## Configuration File

You can define defaults in JSON and still override them from the CLI.

Example `config.json`:

```json
{
  "interval_sec": 0.08,
  "jitter_sec": 0.01,
  "button": "left",
  "double_click": false,
  "click_count": 0,
  "duration_sec": 0,
  "fixed_position": false,
  "x": 0,
  "y": 0,
  "failsafe_corner_stop": true,
  "always_on_top": false,
  "toggle_key": "<f8>",
  "quit_key": "<esc>"
}
```

Run with config:

```bash
python AutoClicker.py --config config.json
```

Config precedence:

1. Built-in defaults
2. JSON config (`--config`)
3. CLI flags (highest priority)

## Build a Single-File Executable (Windows)

Install PyInstaller:

```bash
pip install pyinstaller
```

Build GUI executable (single file, no console window):

```bash
pyinstaller --noconfirm --clean --onefile --windowed --name AutoClick AutoClicker.py
```

Output file:

- `dist\\AutoClick.exe`

Build CLI executable (single file, console):

```bash
pyinstaller --noconfirm --clean --onefile --name AutoClickCLI AutoClicker.py
```

CLI usage example:

```bash
.\\dist\\AutoClickCLI.exe --cli --interval 0.05
```

## Safety and Responsible Use

Use this tool responsibly and only where automation is allowed. Some games, apps, and services prohibit autoclickers and may apply penalties for automated input.

## Troubleshooting

- Hotkeys not working in CLI mode: run in a normal desktop session and ensure input permissions are granted.
- Tkinter import error: install a Python distribution that includes Tk support, or use `--cli` mode.
- macOS users: grant Accessibility/Input Monitoring permissions to your terminal or app.
- Linux users: behavior may vary by display server/session configuration.

## Project Structure

```text
.
+-- AutoClicker.py
+-- Macros.py
+-- README.md
```

## License

Add your preferred license (for example, MIT) in a `LICENSE` file.
