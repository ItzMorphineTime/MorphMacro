# Macro Suite + Autoclicker

Macro-first desktop automation toolkit built in Python, with an included autoclicker companion app.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-green?style=for-the-badge)
![UI](https://img.shields.io/badge/UI-Tkinter-orange?style=for-the-badge)

---

## Overview

This repository contains two apps:

- `Macros.py` (primary): record/play global keyboard and mouse macros with live feedback.
- `AutoClicker.py` (companion): configurable autoclicker with GUI + CLI mode.

If you only need one entry point, start with `Macros.py`.

---

## Macros App (Primary)

`Macros.py` is designed for recording repeatable desktop workflows.

### Core Features

- Global input recording (keyboard + mouse)
- Keyboard press/release capture
- Mouse click press/release capture
- Mouse scroll capture
- Optional mouse movement capture
- Clear runtime states: `IDLE`, `RECORDING`, `PLAYING`
- Live action list with timestamps for every captured step
- Start/stop playback controls (GUI button and hotkey)
- Save/load macros as JSON
- Always-on-top option
- Configurable global hotkeys from the GUI (`Macro Hotkeys` + `Apply Hotkeys`)

### Default Macro Hotkeys

- Start recording: `F9`
- Stop recording: `F10`
- Start playback: `F11`
- Stop playback: `F12`

Hotkeys are editable in the GUI using `pynput` format (for example `<ctrl>+<alt>+r`).

### Typical Workflow

1. Run `python Macros.py`
2. Click `Start Recording` (or press `F9`)
3. Perform actions in any window
4. Stop recording (`F10`)
5. Review recorded action list
6. Play (`F11`) or save as JSON

---

## AutoClicker App (Companion)

`AutoClicker.py` is included when you need focused click automation.

### Core Features

- GUI mode (default) + CLI mode (`--cli`)
- Global toggle/quit hotkeys
- Interval + jitter control
- Left/right/middle button selection
- Optional double-click mode
- Optional click count and duration limits
- Fixed-position mode + coordinate inputs
- Failsafe corner stop
- Always-on-top option (GUI)

### Default AutoClicker Hotkeys

- Toggle: `<f8>`
- Quit: `<esc>`

---

## Requirements

- Python `3.8+`
- `pynput`
- Tkinter (included with most Python installs)

---

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

---

## Quick Start

Run macro tool (primary):

```bash
python Macros.py
```

Run autoclicker GUI:

```bash
python AutoClicker.py
```

Run autoclicker CLI:

```bash
python AutoClicker.py --cli
```

---

## Build Single-File Executables (Windows)

Install PyInstaller:

```bash
pip install pyinstaller
```

Build macro tool:

```bash
pyinstaller --noconfirm --clean --onefile --windowed --name MacroTool Macros.py
```

Build autoclicker GUI:

```bash
pyinstaller --noconfirm --clean --onefile --windowed --name AutoClick AutoClicker.py
```

Build autoclicker CLI:

```bash
pyinstaller --noconfirm --clean --onefile --name AutoClickCLI AutoClicker.py
```

Output binaries are generated in `dist\\`.

---

## Project Structure

```text
.
+-- AutoClicker.py
+-- Macros.py
+-- README.md
```

---

## Safety and Responsible Use

Only automate workflows where automation is allowed. Some games, apps, and services prohibit macro or autoclicker usage and may enforce penalties.

---

## Troubleshooting

- Global hotkeys not firing: verify desktop input/accessibility permissions.
- Tkinter errors: use a Python build with Tk support.
- Linux/macOS input behavior can vary by desktop/session security model.

---
