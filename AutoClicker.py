#!/usr/bin/env python3
"""
Autoclicker with configurable parameters, CLI hotkeys, and a basic GUI.

Defaults:
- Mode: GUI
- CLI toggle hotkey: <f8>
- CLI quit hotkey: <esc>
"""

from __future__ import annotations

import argparse
import json
import random
import threading
import time
from dataclasses import asdict, dataclass
from typing import Optional

from pynput import keyboard, mouse


# =========================
# Easy config (edit here)
# =========================
@dataclass
class ClickConfig:
    interval_sec: float = 0.10          # base time between clicks (0.10 = 10 CPS)
    jitter_sec: float = 0.0             # random +/- jitter added to interval (0 disables)
    button: str = "left"                # left | right | middle
    double_click: bool = False          # if True, double-click each cycle
    click_count: int = 0                # 0 = unlimited, otherwise stop after N clicks
    duration_sec: float = 0.0           # 0 = unlimited, otherwise stop after N seconds
    fixed_position: bool = False        # True = click at (x, y); False = click at current cursor
    x: int = 0                          # fixed X (used only if fixed_position=True)
    y: int = 0                          # fixed Y (used only if fixed_position=True)
    failsafe_corner_stop: bool = True   # stop if mouse is moved to (0, 0)
    always_on_top: bool = False         # keep GUI window above other windows
    toggle_key: str = "<f8>"            # pynput GlobalHotKeys format
    quit_key: str = "<esc>"             # pynput GlobalHotKeys format


DEFAULT_CONFIG = ClickConfig()


# =========================
# Implementation
# =========================
BUTTON_MAP = {
    "left": mouse.Button.left,
    "right": mouse.Button.right,
    "middle": mouse.Button.middle,
}


def clamp_nonnegative(x: float) -> float:
    return x if x > 0 else 0.0


def load_config_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_config(base: ClickConfig, overrides: dict) -> ClickConfig:
    data = asdict(base)
    for k, v in overrides.items():
        if k in data:
            data[k] = v
    return ClickConfig(**data)


class AutoClicker:
    def __init__(self, cfg: ClickConfig):
        self.cfg = cfg
        self.mouse_ctl = mouse.Controller()
        self.button = BUTTON_MAP.get(cfg.button.lower())
        if self.button is None:
            raise ValueError(f"Unsupported button '{cfg.button}'. Use left/right/middle.")

        self._clicking = threading.Event()
        self._stop_all = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)

        self._started_at: Optional[float] = None
        self._clicks_done: int = 0
        self._state_note: str = "Paused."

    def start(self) -> None:
        self._worker.start()

    def toggle(self) -> None:
        if self._clicking.is_set():
            self._clicking.clear()
            self._state_note = "Paused by user."
            print("Clicking paused.")
        else:
            # reset counters on each start
            self._started_at = time.time()
            self._clicks_done = 0
            self._clicking.set()
            self._state_note = "Clicking is active."
            print("Clicking started.")

    def is_clicking(self) -> bool:
        return self._clicking.is_set() and not self._stop_all.is_set()

    def clicks_done(self) -> int:
        return self._clicks_done

    def elapsed_sec(self) -> float:
        if not self._clicking.is_set() or self._started_at is None:
            return 0.0
        return max(0.0, time.time() - self._started_at)

    def state_note(self) -> str:
        return self._state_note

    def stop(self) -> None:
        self._stop_all.set()
        self._clicking.clear()
        self._state_note = "Stopped."

    def _should_stop_for_limits(self) -> bool:
        if self.cfg.duration_sec and self._started_at is not None:
            if (time.time() - self._started_at) >= self.cfg.duration_sec:
                return True
        if self.cfg.click_count and self._clicks_done >= self.cfg.click_count:
            return True
        return False

    def _failsafe_triggered(self) -> bool:
        if not self.cfg.failsafe_corner_stop:
            return False
        try:
            x, y = self.mouse_ctl.position
            return x <= 0 and y <= 0
        except Exception:
            return False

    def _do_click(self) -> None:
        if self.cfg.fixed_position:
            self.mouse_ctl.position = (self.cfg.x, self.cfg.y)

        self.mouse_ctl.click(self.button, 2 if self.cfg.double_click else 1)
        self._clicks_done += 1

    def _sleep_interval(self) -> None:
        base = self.cfg.interval_sec
        jitter = self.cfg.jitter_sec
        if jitter and jitter > 0:
            delay = base + random.uniform(-jitter, jitter)
        else:
            delay = base
        time.sleep(clamp_nonnegative(delay))

    def _run(self) -> None:
        while not self._stop_all.is_set():
            if not self._clicking.is_set():
                time.sleep(0.05)
                continue

            if self._failsafe_triggered():
                self._state_note = "Failsafe triggered: mouse moved to (0, 0)."
                print("Failsafe: mouse at (0, 0). Stopping clicks (press start to resume).")
                self._clicking.clear()
                continue

            if self._should_stop_for_limits():
                self._state_note = "Stopped: click/duration limit reached."
                print("Limit reached. Clicking stopped (press start to restart).")
                self._clicking.clear()
                continue

            self._do_click()
            self._sleep_interval()


def is_valid_hotkey(hotkey: str) -> bool:
    try:
        keyboard.HotKey.parse(hotkey)
        return True
    except ValueError:
        return False


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Configurable autoclicker with GUI or CLI mode.")

    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--gui", action="store_true", help="Run in GUI mode (default).")
    mode.add_argument("--cli", action="store_true", help="Run in CLI hotkey mode.")

    p.add_argument("--config", help="Path to JSON config file (keys match ClickConfig fields).")
    p.add_argument("--interval", type=float, help="Seconds between clicks (e.g., 0.1).")
    p.add_argument("--jitter", type=float, help="Random jitter +/- seconds (e.g., 0.02).")
    p.add_argument("--button", choices=["left", "right", "middle"], help="Mouse button.")
    p.add_argument("--double", action="store_true", help="Double-click each cycle.")
    p.add_argument("--count", type=int, help="Number of clicks (0 = unlimited).")
    p.add_argument("--duration", type=float, help="Run duration in seconds (0 = unlimited).")
    p.add_argument("--fixed", action="store_true", help="Click at a fixed position (x,y).")
    p.add_argument("--x", type=int, help="Fixed X position.")
    p.add_argument("--y", type=int, help="Fixed Y position.")
    p.add_argument("--no-failsafe", action="store_true", help="Disable corner failsafe.")
    p.add_argument("--always-on-top", action="store_true", help="Keep GUI window above other windows.")
    p.add_argument("--toggle-key", help="Hotkey to toggle (pynput format, e.g. <f6>, <ctrl>+<alt>+c).")
    p.add_argument("--quit-key", help="Hotkey to quit (pynput format, default <esc>).")
    return p


def build_config_from_args(args: argparse.Namespace) -> ClickConfig:
    cfg = DEFAULT_CONFIG

    if args.config:
        overrides = load_config_file(args.config)
        cfg = merge_config(cfg, overrides)

    cli_overrides = {}
    if args.interval is not None:
        cli_overrides["interval_sec"] = args.interval
    if args.jitter is not None:
        cli_overrides["jitter_sec"] = args.jitter
    if args.button is not None:
        cli_overrides["button"] = args.button
    if args.double:
        cli_overrides["double_click"] = True
    if args.count is not None:
        cli_overrides["click_count"] = args.count
    if args.duration is not None:
        cli_overrides["duration_sec"] = args.duration
    if args.fixed:
        cli_overrides["fixed_position"] = True
    if args.x is not None:
        cli_overrides["x"] = args.x
    if args.y is not None:
        cli_overrides["y"] = args.y
    if args.no_failsafe:
        cli_overrides["failsafe_corner_stop"] = False
    if args.always_on_top:
        cli_overrides["always_on_top"] = True
    if args.toggle_key is not None:
        cli_overrides["toggle_key"] = args.toggle_key
    if args.quit_key is not None:
        cli_overrides["quit_key"] = args.quit_key

    return merge_config(cfg, cli_overrides)


def run_cli(cfg: ClickConfig) -> None:
    clicker = AutoClicker(cfg)
    clicker.start()

    print("\n=== Autoclicker (CLI Mode) ===")
    print(f"Toggle: {cfg.toggle_key} | Quit: {cfg.quit_key}")
    print(f"Interval: {cfg.interval_sec}s (jitter +/-{cfg.jitter_sec}s)")
    print(f"Button: {cfg.button} | Double: {cfg.double_click}")
    if cfg.fixed_position:
        print(f"Mode: fixed position ({cfg.x}, {cfg.y})")
    else:
        print("Mode: current cursor position")
    if cfg.click_count:
        print(f"Click limit: {cfg.click_count}")
    if cfg.duration_sec:
        print(f"Duration limit: {cfg.duration_sec}s")
    if cfg.failsafe_corner_stop:
        print("Failsafe: move mouse to (0,0) to stop clicking.")
    print("===============================\n")

    def on_toggle() -> None:
        clicker.toggle()

    def on_quit() -> bool:
        print("Quitting...")
        clicker.stop()
        return False

    hotkeys = {
        cfg.toggle_key: on_toggle,
        cfg.quit_key: on_quit,
    }

    with keyboard.GlobalHotKeys(hotkeys) as listener:
        listener.join()

    clicker.stop()


def run_gui(initial_cfg: ClickConfig) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError as exc:
        raise RuntimeError("Tkinter is not available. Run with --cli or install Tk support.") from exc

    class AutoClickerGUI:
        def __init__(self, cfg: ClickConfig):
            self.root = tk.Tk()
            self.root.title("AutoClick - Ready")
            self.root.resizable(False, False)
            self.root.configure(bg="#e5e7eb")

            self.interval_var = tk.StringVar(value=str(cfg.interval_sec))
            self.jitter_var = tk.StringVar(value=str(cfg.jitter_sec))
            self.button_var = tk.StringVar(value=cfg.button)
            self.double_var = tk.BooleanVar(value=cfg.double_click)
            self.count_var = tk.StringVar(value=str(cfg.click_count))
            self.duration_var = tk.StringVar(value=str(cfg.duration_sec))
            self.fixed_var = tk.BooleanVar(value=cfg.fixed_position)
            self.x_var = tk.StringVar(value=str(cfg.x))
            self.y_var = tk.StringVar(value=str(cfg.y))
            self.failsafe_var = tk.BooleanVar(value=cfg.failsafe_corner_stop)
            self.always_on_top_var = tk.BooleanVar(value=cfg.always_on_top)
            self.toggle_key_var = tk.StringVar(value=cfg.toggle_key)
            self.quit_key_var = tk.StringVar(value=cfg.quit_key)
            self.status_var = tk.StringVar(value="Paused by user.")
            self.metrics_var = tk.StringVar(value="Clicks: 0 | Elapsed: 0.0s | CPS: 0.0")
            self.hotkey_status_var = tk.StringVar(value="Global hotkeys are not set.")

            self._clicker = AutoClicker(cfg)
            self._clicker.start()
            self._hotkey_listener: Optional[keyboard.GlobalHotKeys] = None
            self._toggle_btn: Optional[tk.Button] = None
            self._x_entry: Optional[ttk.Entry] = None
            self._y_entry: Optional[ttk.Entry] = None
            self._status_card: Optional[tk.Frame] = None
            self._state_label: Optional[tk.Label] = None
            self._detail_label: Optional[tk.Label] = None
            self._metrics_label: Optional[tk.Label] = None

            self._build_layout(ttk, tk)
            self._update_position_state()
            self._apply_always_on_top()
            if not self._set_hotkeys(cfg.toggle_key, cfg.quit_key):
                self._clicker.stop()
                self.root.destroy()
                raise RuntimeError("Failed to initialize global hotkeys.")
            self.root.protocol("WM_DELETE_WINDOW", self.on_quit)
            self._refresh_feedback()
            self._poll_status()

        def _build_layout(self, ttk_mod, tk_mod) -> None:
            frame = ttk_mod.Frame(self.root, padding=12)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            frame.columnconfigure(1, weight=1)

            self._status_card = tk_mod.Frame(frame, bg="#4b5563", padx=12, pady=10)
            self._status_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

            self._state_label = tk_mod.Label(
                self._status_card,
                text="PAUSED",
                font=("Segoe UI", 14, "bold"),
                bg="#4b5563",
                fg="white",
            )
            self._state_label.grid(row=0, column=0, sticky="w")

            self._detail_label = tk_mod.Label(
                self._status_card,
                textvariable=self.status_var,
                font=("Segoe UI", 10),
                bg="#4b5563",
                fg="white",
            )
            self._detail_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

            self._metrics_label = tk_mod.Label(
                self._status_card,
                textvariable=self.metrics_var,
                font=("Consolas", 10),
                bg="#4b5563",
                fg="#e5e7eb",
            )
            self._metrics_label.grid(row=2, column=0, sticky="w", pady=(4, 0))

            left_panel = ttk_mod.LabelFrame(frame, text="Click Settings", padding=10)
            left_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

            row = 0
            ttk_mod.Label(left_panel, text="Interval (sec)").grid(row=row, column=0, sticky="w", padx=4, pady=4)
            ttk_mod.Entry(left_panel, textvariable=self.interval_var, width=12).grid(row=row, column=1, sticky="w", padx=4, pady=4)

            row += 1
            ttk_mod.Label(left_panel, text="Jitter (+/- sec)").grid(row=row, column=0, sticky="w", padx=4, pady=4)
            ttk_mod.Entry(left_panel, textvariable=self.jitter_var, width=12).grid(row=row, column=1, sticky="w", padx=4, pady=4)

            row += 1
            ttk_mod.Label(left_panel, text="Button").grid(row=row, column=0, sticky="w", padx=4, pady=4)
            ttk_mod.Combobox(
                left_panel,
                textvariable=self.button_var,
                values=["left", "right", "middle"],
                width=10,
                state="readonly",
            ).grid(row=row, column=1, sticky="w", padx=4, pady=4)

            row += 1
            ttk_mod.Checkbutton(left_panel, text="Double click", variable=self.double_var).grid(
                row=row, column=0, columnspan=2, sticky="w", padx=4, pady=4
            )

            row += 1
            ttk_mod.Label(left_panel, text="Click count (0 = unlimited)").grid(row=row, column=0, sticky="w", padx=4, pady=4)
            ttk_mod.Entry(left_panel, textvariable=self.count_var, width=12).grid(row=row, column=1, sticky="w", padx=4, pady=4)

            row += 1
            ttk_mod.Label(left_panel, text="Duration sec (0 = unlimited)").grid(row=row, column=0, sticky="w", padx=4, pady=4)
            ttk_mod.Entry(left_panel, textvariable=self.duration_var, width=12).grid(row=row, column=1, sticky="w", padx=4, pady=4)

            right_panel = ttk_mod.Frame(frame)
            right_panel.grid(row=1, column=1, sticky="nsew")

            position_panel = ttk_mod.LabelFrame(right_panel, text="Position and Safety", padding=10)
            position_panel.grid(row=0, column=0, sticky="ew")

            prow = 0
            ttk_mod.Checkbutton(
                position_panel,
                text="Fixed position",
                variable=self.fixed_var,
                command=self._update_position_state,
            ).grid(
                row=prow, column=0, columnspan=2, sticky="w", padx=4, pady=4
            )

            prow += 1
            ttk_mod.Label(position_panel, text="X").grid(row=prow, column=0, sticky="w", padx=4, pady=4)
            self._x_entry = ttk_mod.Entry(position_panel, textvariable=self.x_var, width=12)
            self._x_entry.grid(row=prow, column=1, sticky="w", padx=4, pady=4)

            prow += 1
            ttk_mod.Label(position_panel, text="Y").grid(row=prow, column=0, sticky="w", padx=4, pady=4)
            self._y_entry = ttk_mod.Entry(position_panel, textvariable=self.y_var, width=12)
            self._y_entry.grid(row=prow, column=1, sticky="w", padx=4, pady=4)

            prow += 1
            ttk_mod.Checkbutton(position_panel, text="Enable (0,0) failsafe", variable=self.failsafe_var).grid(
                row=prow, column=0, columnspan=2, sticky="w", padx=4, pady=4
            )

            prow += 1
            ttk_mod.Checkbutton(
                position_panel,
                text="Always on top",
                variable=self.always_on_top_var,
                command=self._apply_always_on_top,
            ).grid(row=prow, column=0, columnspan=2, sticky="w", padx=4, pady=4)

            hotkey_panel = ttk_mod.LabelFrame(right_panel, text="Hotkeys", padding=10)
            hotkey_panel.grid(row=1, column=0, sticky="ew", pady=(8, 0))

            hrow = 0
            ttk_mod.Label(hotkey_panel, text="Toggle").grid(row=hrow, column=0, sticky="w", padx=4, pady=4)
            ttk_mod.Entry(hotkey_panel, textvariable=self.toggle_key_var, width=16).grid(
                row=hrow, column=1, sticky="w", padx=4, pady=4
            )

            hrow += 1
            ttk_mod.Label(hotkey_panel, text="Quit").grid(row=hrow, column=0, sticky="w", padx=4, pady=4)
            ttk_mod.Entry(hotkey_panel, textvariable=self.quit_key_var, width=16).grid(
                row=hrow, column=1, sticky="w", padx=4, pady=4
            )

            hrow += 1
            ttk_mod.Label(
                hotkey_panel,
                text="Format: <f8> or <ctrl>+<alt>+q",
            ).grid(row=hrow, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 0))

            button_frame = ttk_mod.Frame(frame)
            button_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 6))
            ttk_mod.Button(button_frame, text="Apply Settings", command=self.on_apply).grid(
                row=0, column=0, padx=4
            )
            self._toggle_btn = tk_mod.Button(
                button_frame,
                text="Start Clicking",
                command=self.on_toggle,
                bg="#065f46",
                fg="white",
                activebackground="#047857",
                activeforeground="white",
                relief="flat",
                padx=14,
                pady=6,
            )
            self._toggle_btn.grid(row=0, column=1, padx=4)
            ttk_mod.Button(button_frame, text="Quit", command=self.on_quit).grid(
                row=0, column=2, padx=4
            )

            ttk_mod.Label(
                frame,
                textvariable=self.hotkey_status_var,
                anchor="w",
                justify=tk_mod.LEFT,
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))

            ttk_mod.Label(
                frame,
                text="Tip: You can control the clicker with global hotkeys even when this window is not focused.",
                anchor="w",
                justify=tk_mod.LEFT,
            ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 0))

        def _update_position_state(self) -> None:
            state = "normal" if self.fixed_var.get() else "disabled"
            if self._x_entry is not None:
                self._x_entry.configure(state=state)
            if self._y_entry is not None:
                self._y_entry.configure(state=state)

        def _apply_always_on_top(self) -> None:
            try:
                pin = self.always_on_top_var.get()
                self.root.attributes("-topmost", pin)
                if pin:
                    self.root.lift()
            except tk.TclError:
                self.always_on_top_var.set(False)
                messagebox.showwarning("Window Option", "Always on top is not supported on this platform.")

        def _refresh_feedback(self) -> None:
            running = self._clicker.is_clicking()
            clicks = self._clicker.clicks_done()
            elapsed = self._clicker.elapsed_sec()
            cps = clicks / elapsed if elapsed > 0 else 0.0

            self.status_var.set(self._clicker.state_note())
            self.metrics_var.set(f"Clicks: {clicks} | Elapsed: {elapsed:.1f}s | CPS: {cps:.1f}")

            if running:
                self.root.title("AutoClick - ACTIVE")
                if self._status_card is not None:
                    self._status_card.configure(bg="#065f46")
                if self._state_label is not None:
                    self._state_label.configure(text="ACTIVE", bg="#065f46")
                if self._detail_label is not None:
                    self._detail_label.configure(bg="#065f46", fg="white")
                if self._metrics_label is not None:
                    self._metrics_label.configure(bg="#065f46", fg="#d1fae5")
                if self._toggle_btn is not None:
                    self._toggle_btn.configure(
                        text=f"Pause ({self.toggle_key_var.get().strip()})",
                        bg="#b91c1c",
                        activebackground="#991b1b",
                    )
            else:
                self.root.title("AutoClick - Ready")
                if self._status_card is not None:
                    self._status_card.configure(bg="#4b5563")
                if self._state_label is not None:
                    self._state_label.configure(text="PAUSED", bg="#4b5563")
                if self._detail_label is not None:
                    self._detail_label.configure(bg="#4b5563", fg="white")
                if self._metrics_label is not None:
                    self._metrics_label.configure(bg="#4b5563", fg="#e5e7eb")
                if self._toggle_btn is not None:
                    self._toggle_btn.configure(
                        text=f"Start ({self.toggle_key_var.get().strip()})",
                        bg="#065f46",
                        activebackground="#047857",
                    )

        def _stop_hotkeys(self) -> None:
            if self._hotkey_listener is not None:
                self._hotkey_listener.stop()
                self._hotkey_listener = None

        def _set_hotkeys(self, toggle_key: str, quit_key: str) -> bool:
            if toggle_key == quit_key:
                messagebox.showerror("Invalid hotkeys", "Toggle and quit hotkeys must be different.")
                return False
            if not is_valid_hotkey(toggle_key) or not is_valid_hotkey(quit_key):
                messagebox.showerror(
                    "Invalid hotkey",
                    "Use pynput format such as <f8>, <esc>, or <ctrl>+<alt>+q.",
                )
                return False

            self._stop_hotkeys()

            hotkeys = {
                toggle_key: lambda: self.root.after(0, self.on_toggle),
                quit_key: lambda: self.root.after(0, self.on_quit),
            }
            try:
                self._hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
                self._hotkey_listener.start()
            except ValueError as exc:
                messagebox.showerror("Invalid hotkey", f"Failed to register hotkeys: {exc}")
                self._hotkey_listener = None
                return False

            self.hotkey_status_var.set(f"Global hotkeys active | Toggle: {toggle_key} | Quit: {quit_key}")
            return True

        def _read_config(self):
            try:
                interval = float(self.interval_var.get())
                jitter = float(self.jitter_var.get())
                count = int(self.count_var.get())
                duration = float(self.duration_var.get())
                x = int(self.x_var.get())
                y = int(self.y_var.get())
            except ValueError:
                messagebox.showerror("Invalid input", "Numeric fields must contain valid numbers.")
                return None

            if interval < 0 or jitter < 0 or count < 0 or duration < 0:
                messagebox.showerror("Invalid input", "Interval, jitter, count, and duration must be non-negative.")
                return None

            button = self.button_var.get().strip().lower()
            if button not in BUTTON_MAP:
                messagebox.showerror("Invalid input", "Button must be left, right, or middle.")
                return None

            toggle_key = self.toggle_key_var.get().strip()
            quit_key = self.quit_key_var.get().strip()
            if not toggle_key or not quit_key:
                messagebox.showerror("Invalid input", "Toggle and quit hotkeys are required.")
                return None
            if toggle_key == quit_key:
                messagebox.showerror("Invalid input", "Toggle and quit hotkeys must be different.")
                return None
            if not is_valid_hotkey(toggle_key) or not is_valid_hotkey(quit_key):
                messagebox.showerror(
                    "Invalid hotkey",
                    "Use pynput format such as <f8>, <esc>, or <ctrl>+<alt>+q.",
                )
                return None

            return ClickConfig(
                interval_sec=interval,
                jitter_sec=jitter,
                button=button,
                double_click=self.double_var.get(),
                click_count=count,
                duration_sec=duration,
                fixed_position=self.fixed_var.get(),
                x=x,
                y=y,
                failsafe_corner_stop=self.failsafe_var.get(),
                always_on_top=self.always_on_top_var.get(),
                toggle_key=toggle_key,
                quit_key=quit_key,
            )

        def on_apply(self) -> None:
            cfg = self._read_config()
            if cfg is None:
                return
            if not self._set_hotkeys(cfg.toggle_key, cfg.quit_key):
                return

            was_running = self._clicker.is_clicking()
            self._clicker.stop()
            self._clicker = AutoClicker(cfg)
            self._clicker.start()
            if was_running:
                self._clicker.toggle()
            else:
                self.status_var.set("Settings applied.")
            self._update_position_state()
            self._apply_always_on_top()
            self._refresh_feedback()

        def on_toggle(self) -> None:
            self._clicker.toggle()
            self._refresh_feedback()

        def _poll_status(self) -> None:
            if self.root.winfo_exists():
                self._refresh_feedback()
                self.root.after(250, self._poll_status)

        def on_quit(self) -> None:
            self._stop_hotkeys()
            self._clicker.stop()
            if self.root.winfo_exists():
                self.root.destroy()

        def run(self) -> None:
            self.root.mainloop()

    app = AutoClickerGUI(initial_cfg)
    app.run()


def main() -> None:
    args = build_arg_parser().parse_args()
    cfg = build_config_from_args(args)

    if args.cli:
        run_cli(cfg)
    else:
        run_gui(cfg)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
