#!/usr/bin/env python3
"""
Autoclicker with configurable parameters + hotkeys.

Defaults:
- Toggle clicking: F6
- Quit: Esc
"""

from __future__ import annotations

import argparse
import json
import random
import threading
import time
from dataclasses import dataclass, asdict
from typing import Optional, Tuple

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

    def start(self) -> None:
        self._worker.start()

    def toggle(self) -> None:
        if self._clicking.is_set():
            self._clicking.clear()
            print("⏸️  Clicking paused.")
        else:
            # reset counters on each start
            self._started_at = time.time()
            self._clicks_done = 0
            self._clicking.set()
            print("▶️  Clicking started.")

    def stop(self) -> None:
        self._stop_all.set()
        self._clicking.clear()

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

        # single click
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
                print("🛑 Failsafe: mouse at (0, 0). Stopping clicks (press toggle to resume).")
                self._clicking.clear()
                continue

            if self._should_stop_for_limits():
                print("✅ Limit reached. Clicking stopped (press toggle to restart).")
                self._clicking.clear()
                continue

            self._do_click()
            self._sleep_interval()


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Configurable autoclicker (toggle hotkey + quit hotkey).")
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
    p.add_argument("--toggle-key", help="Hotkey to toggle (pynput format, e.g. <f6>, <ctrl>+<alt>+c).")
    p.add_argument("--quit-key", help="Hotkey to quit (pynput format, default <esc>).")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()

    cfg = DEFAULT_CONFIG

    # 1) Config file (optional)
    if args.config:
        overrides = load_config_file(args.config)
        cfg = merge_config(cfg, overrides)

    # 2) CLI overrides (optional)
    cli_overrides = {}
    if args.interval is not None: cli_overrides["interval_sec"] = args.interval
    if args.jitter is not None: cli_overrides["jitter_sec"] = args.jitter
    if args.button is not None: cli_overrides["button"] = args.button
    if args.double: cli_overrides["double_click"] = True
    if args.count is not None: cli_overrides["click_count"] = args.count
    if args.duration is not None: cli_overrides["duration_sec"] = args.duration
    if args.fixed: cli_overrides["fixed_position"] = True
    if args.x is not None: cli_overrides["x"] = args.x
    if args.y is not None: cli_overrides["y"] = args.y
    if args.no_failsafe: cli_overrides["failsafe_corner_stop"] = False
    if args.toggle_key is not None: cli_overrides["toggle_key"] = args.toggle_key
    if args.quit_key is not None: cli_overrides["quit_key"] = args.quit_key

    cfg = merge_config(cfg, cli_overrides)

    clicker = AutoClicker(cfg)
    clicker.start()

    print("\n=== Autoclicker ===")
    print(f"Toggle: {cfg.toggle_key} | Quit: {cfg.quit_key}")
    print(f"Interval: {cfg.interval_sec}s (jitter ±{cfg.jitter_sec}s)")
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
    print("===================\n")

    def on_toggle():
        clicker.toggle()

    def on_quit():
        print("👋 Quitting...")
        clicker.stop()
        exit()
        return False  # stop listener

    hotkeys = {
        cfg.toggle_key: on_toggle,
        cfg.quit_key: on_quit,
    }

    # GlobalHotKeys runs until on_quit returns False
    with keyboard.GlobalHotKeys(hotkeys) as listener:
        listener.join()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
