#!/usr/bin/env python3
"""
Macro recorder with live feedback and action list.

Features:
- Record global keyboard and mouse actions
- Show every recorded action in a list
- Playback recorded actions
- Save/load macros as JSON
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pynput import keyboard, mouse


@dataclass
class UIEvent:
    kind: str
    payload: Any = None


class MacroApp:
    RECORD_START_HOTKEY = "<f9>"
    RECORD_STOP_HOTKEY = "<f10>"
    PLAY_START_HOTKEY = "<f11>"
    PLAY_STOP_HOTKEY = "<f12>"

    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = tk.Tk()
        self.root.title("Macro Recorder - Ready")
        self.root.resizable(False, False)
        self.root.configure(bg="#e5e7eb")

        self.status_var = tk.StringVar(
            value=(
                "Idle: Start Record F9 | Stop Record F10 | "
                "Play F11 | Stop Play F12"
            )
        )
        self.metrics_var = tk.StringVar(value="Actions: 0 | Duration: 0.0s")
        self.options_var = tk.StringVar(value="Mouse moves are not being recorded.")
        self.hotkeys_var = tk.StringVar(
            value="Global hotkeys: Record F9/F10 | Play F11/F12"
        )
        self.record_start_hotkey_var = tk.StringVar(value=self.RECORD_START_HOTKEY)
        self.record_stop_hotkey_var = tk.StringVar(value=self.RECORD_STOP_HOTKEY)
        self.play_start_hotkey_var = tk.StringVar(value=self.PLAY_START_HOTKEY)
        self.play_stop_hotkey_var = tk.StringVar(value=self.PLAY_STOP_HOTKEY)
        self.capture_moves_var = tk.BooleanVar(value=False)
        self.topmost_var = tk.BooleanVar(value=False)
        self._capture_moves = False

        self.actions: list[dict[str, Any]] = []
        self._queue: queue.Queue[UIEvent] = queue.Queue()
        self._recording = False
        self._playing = False
        self._record_started_at = 0.0
        self._last_move_log_t = 0.0
        self._last_move_pos: Optional[tuple[int, int]] = None

        self._mouse_listener: Optional[mouse.Listener] = None
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._hotkey_listener: Optional[keyboard.GlobalHotKeys] = None
        self._playback_thread: Optional[threading.Thread] = None
        self._playback_stop = threading.Event()
        self._hotkey_parts: list[Any] = []

        self._build_ui()
        if not self._apply_hotkeys(show_message=False):
            raise RuntimeError("Failed to initialize global hotkeys.")
        self._refresh_feedback()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(50, self._drain_queue)

    def _build_ui(self) -> None:
        tk = self.tk
        ttk = self.ttk

        container = ttk.Frame(self.root, padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)

        self.status_card = tk.Frame(container, bg="#4b5563", padx=12, pady=10)
        self.status_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.state_label = tk.Label(
            self.status_card,
            text="IDLE",
            bg="#4b5563",
            fg="white",
            font=("Segoe UI", 14, "bold"),
        )
        self.state_label.grid(row=0, column=0, sticky="w")
        self.detail_label = tk.Label(
            self.status_card,
            textvariable=self.status_var,
            bg="#4b5563",
            fg="white",
            font=("Segoe UI", 10),
        )
        self.detail_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.metrics_label = tk.Label(
            self.status_card,
            textvariable=self.metrics_var,
            bg="#4b5563",
            fg="#e5e7eb",
            font=("Consolas", 10),
        )
        self.metrics_label.grid(row=2, column=0, sticky="w", pady=(4, 0))

        control_frame = ttk.LabelFrame(container, text="Controls", padding=10)
        control_frame.grid(row=1, column=0, sticky="ew")

        self.start_btn = tk.Button(
            control_frame,
            text="Start Recording",
            command=self.start_recording,
            bg="#065f46",
            fg="white",
            activebackground="#047857",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=6,
        )
        self.start_btn.grid(row=0, column=0, padx=4, pady=4)

        self.stop_btn = ttk.Button(control_frame, text="Stop Recording", command=self.stop_recording)
        self.stop_btn.grid(row=0, column=1, padx=4, pady=4)

        self.play_btn = ttk.Button(control_frame, text="Play Macro", command=self.play_macro)
        self.play_btn.grid(row=0, column=2, padx=4, pady=4)

        self.stop_play_btn = ttk.Button(control_frame, text="Stop Playback", command=self.stop_playback)
        self.stop_play_btn.grid(row=0, column=3, padx=4, pady=4)

        self.clear_btn = ttk.Button(control_frame, text="Clear", command=self.clear_actions)
        self.clear_btn.grid(row=0, column=4, padx=4, pady=4)

        self.save_btn = ttk.Button(control_frame, text="Save JSON", command=self.save_macro)
        self.save_btn.grid(row=0, column=5, padx=4, pady=4)

        self.load_btn = ttk.Button(control_frame, text="Load JSON", command=self.load_macro)
        self.load_btn.grid(row=0, column=6, padx=4, pady=4)

        options_frame = ttk.LabelFrame(container, text="Options", padding=10)
        options_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Checkbutton(
            options_frame,
            text="Record mouse movement",
            variable=self.capture_moves_var,
            command=self._on_option_change,
        ).grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(
            options_frame,
            text="Always on top",
            variable=self.topmost_var,
            command=self._apply_topmost,
        ).grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(options_frame, textvariable=self.options_var).grid(row=2, column=0, sticky="w", padx=4, pady=(4, 0))
        ttk.Label(options_frame, textvariable=self.hotkeys_var).grid(row=3, column=0, sticky="w", padx=4, pady=(4, 0))

        hotkey_frame = ttk.LabelFrame(container, text="Macro Hotkeys", padding=10)
        hotkey_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(hotkey_frame, text="Record start").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(hotkey_frame, textvariable=self.record_start_hotkey_var, width=18).grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )
        ttk.Label(hotkey_frame, text="Record stop").grid(row=0, column=2, sticky="w", padx=12, pady=2)
        ttk.Entry(hotkey_frame, textvariable=self.record_stop_hotkey_var, width=18).grid(
            row=0, column=3, sticky="w", padx=4, pady=2
        )
        ttk.Label(hotkey_frame, text="Play start").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(hotkey_frame, textvariable=self.play_start_hotkey_var, width=18).grid(
            row=1, column=1, sticky="w", padx=4, pady=2
        )
        ttk.Label(hotkey_frame, text="Play stop").grid(row=1, column=2, sticky="w", padx=12, pady=2)
        ttk.Entry(hotkey_frame, textvariable=self.play_stop_hotkey_var, width=18).grid(
            row=1, column=3, sticky="w", padx=4, pady=2
        )
        ttk.Button(hotkey_frame, text="Apply Hotkeys", command=self.apply_hotkeys).grid(
            row=2, column=0, columnspan=4, sticky="w", padx=4, pady=(8, 0)
        )
        ttk.Label(
            hotkey_frame,
            text="Use pynput format, for example <f9> or <ctrl>+<alt>+p",
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=4, pady=(4, 0))

        list_frame = ttk.LabelFrame(container, text="Recorded Actions", padding=10)
        list_frame.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.action_list = tk.Listbox(
            list_frame,
            width=110,
            height=18,
            font=("Consolas", 10),
        )
        self.action_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.action_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.action_list.configure(yscrollcommand=scrollbar.set)

    def _set_card_style(self, *, bg: str, fg: str, metric_fg: str, state_text: str) -> None:
        self.status_card.configure(bg=bg)
        self.state_label.configure(text=state_text, bg=bg, fg=fg)
        self.detail_label.configure(bg=bg, fg=fg)
        self.metrics_label.configure(bg=bg, fg=metric_fg)

    def _refresh_feedback(self) -> None:
        duration = self.actions[-1]["t"] if self.actions else 0.0
        self.metrics_var.set(f"Actions: {len(self.actions)} | Duration: {duration:.3f}s")

        if self._recording:
            self.root.title("Macro Recorder - RECORDING")
            self._set_card_style(bg="#9a3412", fg="white", metric_fg="#ffedd5", state_text="RECORDING")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.play_btn.configure(state="disabled")
            self.stop_play_btn.configure(state="disabled")
            self.clear_btn.configure(state="disabled")
            self.save_btn.configure(state="disabled")
            self.load_btn.configure(state="disabled")
        elif self._playing:
            self.root.title("Macro Recorder - PLAYING")
            self._set_card_style(bg="#1d4ed8", fg="white", metric_fg="#dbeafe", state_text="PLAYING")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
            self.play_btn.configure(state="disabled")
            self.stop_play_btn.configure(state="normal")
            self.clear_btn.configure(state="disabled")
            self.save_btn.configure(state="disabled")
            self.load_btn.configure(state="disabled")
        else:
            self.root.title("Macro Recorder - Ready")
            self._set_card_style(bg="#4b5563", fg="white", metric_fg="#e5e7eb", state_text="IDLE")
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.play_btn.configure(state="normal" if self.actions else "disabled")
            self.stop_play_btn.configure(state="disabled")
            self.clear_btn.configure(state="normal")
            self.save_btn.configure(state="normal" if self.actions else "disabled")
            self.load_btn.configure(state="normal")

    def _on_option_change(self) -> None:
        self._capture_moves = bool(self.capture_moves_var.get())
        if self._capture_moves:
            self.options_var.set("Mouse moves are being recorded.")
        else:
            self.options_var.set("Mouse moves are not being recorded.")

    def _apply_topmost(self) -> None:
        try:
            self.root.attributes("-topmost", self.topmost_var.get())
            if self.topmost_var.get():
                self.root.lift()
        except self.tk.TclError:
            self.topmost_var.set(False)

    @staticmethod
    def _normalize_hotkey_text(value: str) -> str:
        return value.strip().lower().replace(" ", "")

    @staticmethod
    def _keycode_matches(a: keyboard.KeyCode, b: keyboard.KeyCode) -> bool:
        if a.vk is not None and b.vk is not None:
            return a.vk == b.vk
        if a.char is not None and b.char is not None:
            return a.char.lower() == b.char.lower()
        return False

    def _hotkey_part_matches_key(self, part: Any, key: keyboard.Key | keyboard.KeyCode) -> bool:
        if isinstance(part, keyboard.Key):
            return key == part

        if isinstance(part, keyboard.KeyCode):
            if isinstance(key, keyboard.KeyCode):
                return self._keycode_matches(part, key)
            if isinstance(key, keyboard.Key) and isinstance(key.value, keyboard.KeyCode):
                return self._keycode_matches(part, key.value)
            return False

        if isinstance(part, str):
            if isinstance(key, keyboard.KeyCode) and key.char is not None:
                return key.char.lower() == part.lower()
            if isinstance(key, keyboard.Key) and isinstance(key.value, keyboard.KeyCode) and key.value.char is not None:
                return key.value.char.lower() == part.lower()
            return False

        return False

    def _should_suppress_key(self, key: keyboard.Key | keyboard.KeyCode) -> bool:
        for part in self._hotkey_parts:
            if self._hotkey_part_matches_key(part, key):
                return True
        return False

    def _build_hotkey_bindings(self) -> tuple[dict[str, Any], list[Any]]:
        values = {
            "record_start": self.record_start_hotkey_var.get().strip(),
            "record_stop": self.record_stop_hotkey_var.get().strip(),
            "play_start": self.play_start_hotkey_var.get().strip(),
            "play_stop": self.play_stop_hotkey_var.get().strip(),
        }

        for name, raw in values.items():
            if not raw:
                raise ValueError(f"{name.replace('_', ' ').title()} hotkey is required.")

        normalized = [self._normalize_hotkey_text(v) for v in values.values()]
        if len(set(normalized)) != 4:
            raise ValueError("All macro hotkeys must be unique.")

        suppress_parts: list[Any] = []
        for name, raw in values.items():
            try:
                parsed = keyboard.HotKey.parse(raw)
            except ValueError as exc:
                pretty = name.replace("_", " ").title()
                raise ValueError(f"Invalid {pretty} hotkey: {exc}") from exc
            # Suppress recording only for single-key hotkeys; multi-key combos are not suppressed
            # to avoid hiding common keys like letters/modifiers during normal recording.
            if len(parsed) == 1:
                suppress_parts.extend(parsed)

        bindings = {
            values["record_start"]: lambda: self.root.after(0, self.start_recording),
            values["record_stop"]: lambda: self.root.after(0, self.stop_recording),
            values["play_start"]: lambda: self.root.after(0, self.play_macro),
            values["play_stop"]: lambda: self.root.after(0, self.stop_playback),
        }
        return bindings, suppress_parts

    def _start_hotkeys(self, bindings: dict[str, Any]) -> None:
        self._stop_hotkeys()
        self._hotkey_listener = keyboard.GlobalHotKeys(bindings)
        self._hotkey_listener.start()

    def _stop_hotkeys(self) -> None:
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

    def _set_hotkey_status_text(self) -> None:
        self.hotkeys_var.set(
            "Global hotkeys: "
            f"Record {self.record_start_hotkey_var.get().strip()}/"
            f"{self.record_stop_hotkey_var.get().strip()} | "
            f"Play {self.play_start_hotkey_var.get().strip()}/"
            f"{self.play_stop_hotkey_var.get().strip()}"
        )

    def _apply_hotkeys(self, show_message: bool) -> bool:
        from tkinter import messagebox

        try:
            bindings, parsed_parts = self._build_hotkey_bindings()
            self._start_hotkeys(bindings)
        except Exception as exc:
            if show_message:
                messagebox.showerror("Invalid hotkeys", str(exc))
            return False

        self._hotkey_parts = parsed_parts
        self._set_hotkey_status_text()
        if show_message:
            self.status_var.set("Hotkeys updated.")
        return True

    def apply_hotkeys(self) -> None:
        self._apply_hotkeys(show_message=True)

    def _event_time(self) -> float:
        return max(0.0, time.perf_counter() - self._record_started_at)

    def _record_event(self, action: dict[str, Any]) -> None:
        if not self._recording:
            return
        action["t"] = round(self._event_time(), 6)
        self.actions.append(action)
        self._queue.put(UIEvent("action_added", action))

    @staticmethod
    def _serialize_key(key: keyboard.Key | keyboard.KeyCode) -> dict[str, Any]:
        if isinstance(key, keyboard.KeyCode):
            if key.char is not None:
                return {"key_type": "char", "value": key.char}
            if key.vk is not None:
                return {"key_type": "vk", "value": key.vk}
            return {"key_type": "text", "value": str(key)}
        if isinstance(key, keyboard.Key):
            return {"key_type": "special", "value": key.name}
        return {"key_type": "text", "value": str(key)}

    @staticmethod
    def _deserialize_key(payload: dict[str, Any]) -> Optional[keyboard.Key | keyboard.KeyCode]:
        key_type = payload.get("key_type")
        value = payload.get("value")
        if key_type == "char" and isinstance(value, str) and value:
            return keyboard.KeyCode.from_char(value)
        if key_type == "vk" and isinstance(value, int):
            return keyboard.KeyCode.from_vk(value)
        if key_type == "special" and isinstance(value, str) and hasattr(keyboard.Key, value):
            return getattr(keyboard.Key, value)
        return None

    @staticmethod
    def _button_from_name(name: str) -> mouse.Button:
        if hasattr(mouse.Button, name):
            return getattr(mouse.Button, name)
        return mouse.Button.left

    @staticmethod
    def _format_action(idx: int, action: dict[str, Any]) -> str:
        t = action.get("t", 0.0)
        kind = action.get("kind", "unknown")

        if kind == "mouse_move":
            text = f"mouse_move  x={action.get('x')} y={action.get('y')}"
        elif kind == "mouse_click":
            phase = "down" if action.get("pressed") else "up"
            text = f"mouse_click {phase} {action.get('button')} at ({action.get('x')}, {action.get('y')})"
        elif kind == "mouse_scroll":
            text = f"mouse_scroll dx={action.get('dx')} dy={action.get('dy')} at ({action.get('x')}, {action.get('y')})"
        elif kind == "key":
            phase = action.get("phase", "?")
            key_type = action.get("key_type", "unknown")
            value = action.get("value")
            text = f"key_{phase} {key_type}:{value}"
        else:
            text = json.dumps(action, ensure_ascii=True)
        return f"{idx:04d} | +{t:08.3f}s | {text}"

    def start_recording(self) -> None:
        from tkinter import messagebox

        if self._playing:
            messagebox.showwarning("Playback running", "Wait for playback to finish before recording.")
            return

        if self._recording:
            return

        self.actions.clear()
        self.action_list.delete(0, self.tk.END)
        self._record_started_at = time.perf_counter()
        self._last_move_log_t = 0.0
        self._last_move_pos = None
        self._recording = True
        self.status_var.set("Recording... perform actions in any window.")
        self._on_option_change()

        self._mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll,
        )
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener.start()
        self._keyboard_listener.start()
        self._refresh_feedback()

    def stop_recording(self) -> None:
        if not self._recording:
            return
        self._recording = False
        self._stop_listeners()
        self.status_var.set(f"Recording stopped. Captured {len(self.actions)} actions.")
        self._refresh_feedback()

    def _stop_listeners(self) -> None:
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    def clear_actions(self) -> None:
        if self._recording:
            self.stop_recording()
        self.actions.clear()
        self.action_list.delete(0, self.tk.END)
        self.status_var.set("Cleared all actions.")
        self._refresh_feedback()

    def save_macro(self) -> None:
        from tkinter import filedialog, messagebox

        if not self.actions:
            messagebox.showinfo("No actions", "Record a macro before saving.")
            return
        path = filedialog.asksaveasfilename(
            title="Save macro",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        payload = {"version": 1, "actions": self.actions}
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.status_var.set(f"Saved macro: {path}")

    def load_macro(self) -> None:
        from tkinter import filedialog, messagebox

        if self._recording:
            self.stop_recording()
        path = filedialog.askopenfilename(
            title="Load macro",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            actions = data["actions"] if isinstance(data, dict) else data
            if not isinstance(actions, list):
                raise ValueError("Invalid macro format: actions must be a list.")
            self.actions = [a for a in actions if isinstance(a, dict)]
        except Exception as exc:
            messagebox.showerror("Load failed", f"Could not load macro:\n{exc}")
            return

        self.action_list.delete(0, self.tk.END)
        for idx, action in enumerate(self.actions, start=1):
            self.action_list.insert(self.tk.END, self._format_action(idx, action))
        if self.actions:
            self.action_list.see(self.tk.END)
        self.status_var.set(f"Loaded macro: {path} ({len(self.actions)} actions)")
        self._refresh_feedback()

    def play_macro(self) -> None:
        from tkinter import messagebox

        if self._recording:
            messagebox.showwarning("Recording active", "Stop recording before playback.")
            return
        if self._playing:
            return
        if not self.actions:
            messagebox.showinfo("No actions", "Record or load a macro first.")
            return

        self._playback_stop.clear()
        self._playing = True
        self.status_var.set("Playing back macro...")
        self._refresh_feedback()
        self._playback_thread = threading.Thread(target=self._play_worker, daemon=True)
        self._playback_thread.start()

    def stop_playback(self) -> None:
        if not self._playing:
            return
        self._playback_stop.set()
        self.status_var.set("Stopping playback...")
        self._refresh_feedback()

    def _play_worker(self) -> None:
        mouse_ctl = mouse.Controller()
        key_ctl = keyboard.Controller()
        prev_t = 0.0

        try:
            for action in list(self.actions):
                if self._playback_stop.is_set():
                    self._queue.put(UIEvent("playback_stopped"))
                    return

                t = float(action.get("t", 0.0))
                delay = max(0.0, t - prev_t)
                if delay:
                    if self._playback_stop.wait(delay):
                        self._queue.put(UIEvent("playback_stopped"))
                        return
                if self._playback_stop.is_set():
                    self._queue.put(UIEvent("playback_stopped"))
                    return
                prev_t = t
                self._execute_action(mouse_ctl, key_ctl, action)
        except Exception as exc:
            self._queue.put(UIEvent("playback_error", str(exc)))
            return

        self._queue.put(UIEvent("playback_done"))

    def _execute_action(
        self,
        mouse_ctl: mouse.Controller,
        key_ctl: keyboard.Controller,
        action: dict[str, Any],
    ) -> None:
        kind = action.get("kind")
        if kind == "mouse_move":
            mouse_ctl.position = (int(action.get("x", 0)), int(action.get("y", 0)))
            return
        if kind == "mouse_click":
            btn = self._button_from_name(str(action.get("button", "left")))
            if action.get("pressed"):
                mouse_ctl.press(btn)
            else:
                mouse_ctl.release(btn)
            return
        if kind == "mouse_scroll":
            mouse_ctl.scroll(int(action.get("dx", 0)), int(action.get("dy", 0)))
            return
        if kind == "key":
            key_obj = self._deserialize_key(action)
            if key_obj is None:
                return
            if action.get("phase") == "press":
                key_ctl.press(key_obj)
            else:
                key_ctl.release(key_obj)

    def _on_mouse_move(self, x: int, y: int) -> None:
        if not self._capture_moves:
            return

        now_t = self._event_time()
        if now_t - self._last_move_log_t < 0.02:
            return
        if self._last_move_pos is not None:
            dx = abs(self._last_move_pos[0] - x)
            dy = abs(self._last_move_pos[1] - y)
            if dx + dy < 2:
                return

        self._last_move_log_t = now_t
        self._last_move_pos = (x, y)
        self._record_event({"kind": "mouse_move", "x": x, "y": y})

    def _on_mouse_click(self, x: int, y: int, btn: mouse.Button, pressed: bool) -> None:
        self._record_event(
            {
                "kind": "mouse_click",
                "x": x,
                "y": y,
                "button": btn.name,
                "pressed": bool(pressed),
            }
        )

    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        self._record_event({"kind": "mouse_scroll", "x": x, "y": y, "dx": dx, "dy": dy})

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if self._should_suppress_key(key):
            return
        payload = self._serialize_key(key)
        payload["kind"] = "key"
        payload["phase"] = "press"
        self._record_event(payload)

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        if self._should_suppress_key(key):
            return
        payload = self._serialize_key(key)
        payload["kind"] = "key"
        payload["phase"] = "release"
        self._record_event(payload)

    def _drain_queue(self) -> None:
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                break

            if event.kind == "action_added":
                idx = len(self.actions)
                if isinstance(event.payload, dict):
                    line = self._format_action(idx, event.payload)
                    self.action_list.insert(self.tk.END, line)
                    self.action_list.see(self.tk.END)
                self._refresh_feedback()
            elif event.kind == "playback_done":
                self._playing = False
                self.status_var.set("Playback complete.")
                self._refresh_feedback()
            elif event.kind == "playback_stopped":
                self._playing = False
                self.status_var.set("Playback stopped.")
                self._refresh_feedback()
            elif event.kind == "playback_error":
                self._playing = False
                self.status_var.set(f"Playback failed: {event.payload}")
                self._refresh_feedback()

        if self.root.winfo_exists():
            self.root.after(50, self._drain_queue)

    def on_close(self) -> None:
        self._recording = False
        self._playback_stop.set()
        self._stop_listeners()
        self._stop_hotkeys()
        if self.root.winfo_exists():
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = MacroApp()
    app.run()


if __name__ == "__main__":
    main()
