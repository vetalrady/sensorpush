"""SensorPush GUI – Temperature under‑64°F percentage (last 24 hours)
=================================================================
Tkinter dashboard that logs into your SensorPush Cloud account and shows,
for each sensor, what **percentage of the last‑24‑hour temperature samples
were below 64 °F**. Every individual reading is still printed to the Debug
Log for traceability.
"""

from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta, timezone
from tkinter import ttk, messagebox
from pathlib import Path
import logging
from typing import List, Dict, Optional


import requests

API_BASE = "https://api.sensorpush.com/api/v1"
UTC = timezone.utc

# Default credentials used to pre-fill the login fields in the GUI. Change
# these values if you want different hard coded credentials. They are only
# used as the initial values for the corresponding ``StringVar`` objects and
# can still be edited by the user.
DEFAULT_EMAIL = "user@example.com"
DEFAULT_PASSWORD = "change-me"

# ---------- logging ---------- #
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ==================== API client ==================== #
class SensorPushClient:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.access_token: Optional[str] = None
        self.last_list_payload: Optional[dict] = None
        self.last_samples_payload: Optional[dict] = None

    # ---- OAuth ---- #
    def login(self):
        code = self._authorize()
        self._exchange_token(code)

    def _authorize(self) -> str:
        resp = self.session.post(f"{API_BASE}/oauth/authorize", json={"email": self.email, "password": self.password}, timeout=10)
        resp.raise_for_status()
        code = resp.json().get("authorization")
        if not code:
            raise RuntimeError("Authorization failed – check credentials")
        return code

    def _exchange_token(self, code: str):
        resp = self.session.post(f"{API_BASE}/oauth/accesstoken", json={"authorization": code}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self.access_token = data["accesstoken"]
        self.session.headers.update({"Authorization": self.access_token})

    # ---- Data ---- #
    def list_sensors(self) -> List[Dict]:
        resp = self.session.post(f"{API_BASE}/devices/sensors", json={}, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        self.last_list_payload = payload
        raw = payload.get("sensors") if isinstance(payload, dict) else None
        if raw is None:
            raw = payload
        return list(raw.values()) if isinstance(raw, dict) else raw

    def samples_last_24h(self, sensor_ids: Optional[List[str]] = None) -> List[Dict]:
        end = datetime.now(tz=UTC)
        start = end - timedelta(hours=24)
        body: Dict[str, object] = {
            "limit": 3000,
            "startTime": start.isoformat(timespec="seconds"),
            "endTime": end.isoformat(timespec="seconds"),
        }
        if sensor_ids:
            body["sensors"] = sensor_ids
        resp = self.session.post(f"{API_BASE}/samples", json=body, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        self.last_samples_payload = data
        raw = data.get("samples") or data.get("sensors", {})
        flat: List[Dict] = []
        if isinstance(raw, list):
            for s in raw:
                s.setdefault("sensor", s.get("sensor_id"))
                flat.append(s)
        else:  # dict keyed by sensor id
            for sid, lst in raw.items():
                for s in lst:
                    s["sensor"] = sid
                    flat.append(s)
        return flat


# ==================== GUI ==================== #
class SensorPushGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SensorPush – % Temps < 64 °F (24 h)")
        # Let the window expand naturally so the optional layout overlay
        # is fully visible. Use a minimum size to keep the base UI usable.
        self.minsize(760, 620)
        self.client: Optional[SensorPushClient] = None
        self.sensors: Dict[str, Dict] = {}
        # Raw temperature samples keyed by sensor id for the last fetch
        self.samples_by_sensor: Dict[str, List[tuple[datetime, float]]] = {}
        self.layout_img: Optional[tk.PhotoImage] = None
        self.canvas: Optional[tk.Canvas] = None
        # Debug log widget removed; keep attribute for _log method
        self.log: Optional[tk.Text] = None
        # matplotlib objects lazily imported
        self.Figure = None
        self.FigureCanvasTkAgg = None
        # Positions on the layout image keyed **by sensor name**.
        # Add your own sensor names here with (x, y) coordinates.
        self.sensor_positions: Dict[str, tuple[int, int]] = {
            "1": (330, 400),
            "2": (430, 400),
            "3": (530, 200),
            "4": (530, 600),
            "5": (160, 500),
        }
        self._build_ui()
        # start fetching automatically after UI loads
        self.after(100, self._start_fetch)

    def _show_loading(self, msg: str = "Loading…"):
        """Overlay a translucent message on the layout canvas."""
        if not self.canvas or not self.layout_img:
            return
        width = self.layout_img.width()
        height = self.layout_img.height()
        self.canvas.delete("loading_overlay")
        self.canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill="#000",
            stipple="gray50",
            tags="loading_overlay",
        )
        self.canvas.create_text(
            width // 2,
            height // 2,
            text=msg,
            fill="white",
            font=("TkDefaultFont", 16, "bold"),
            tags="loading_overlay",
        )
        self.update_idletasks()

    def _hide_loading(self):
        if self.canvas:
            self.canvas.delete("loading_overlay")

    # ---- UI ---- #
    def _build_ui(self):
        # Only the layout overlay is displayed; login is automatic
        img_path = Path("layout.png")
        if img_path.exists():
            self._log(f"layout.png found at {img_path.resolve()}")
            try:
                self.layout_img = tk.PhotoImage(file=str(img_path))
                self._log(
                    f"layout.png loaded ({self.layout_img.width()}x{self.layout_img.height()})"
                )
                lf_layout = ttk.LabelFrame(self, text="Layout")
                lf_layout.pack(fill="both", expand=True, padx=10, pady=(0, 10))
                self.canvas = tk.Canvas(
                    lf_layout,
                    width=self.layout_img.width(),
                    height=self.layout_img.height(),
                )
                self.canvas.create_image(0, 0, image=self.layout_img, anchor="nw")
                self.canvas.pack()
                self.canvas.tag_bind("sensor_box", "<Double-Button-1>", self._on_sensor_double)
            except Exception as e:
                self._log(f"Failed to load layout.png: {e}")
        else:
            self._log("layout.png not found")

    # ---- helpers ---- #
    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        if self.log is not None:
            self.log.configure(state="normal")
            self.log.insert("end", f"{ts} – {msg}\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        logger.info(msg)

    # ---- event handlers ---- #
    def _start_fetch(self):
        # Import matplotlib lazily when fetching begins
        if self.Figure is None:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            self.Figure = Figure
            self.FigureCanvasTkAgg = FigureCanvasTkAgg

        # Show loading overlay before blocking network requests
        self._show_loading("Fetching data…")

        self._log("Logging in…")
        self.client = SensorPushClient(DEFAULT_EMAIL, DEFAULT_PASSWORD)
        try:
            self.client.login()
        except Exception as e:
            self._log(f"Login failed: {e}"); return
        self._log("Login success. Getting sensors…")
        try:
            sensors = self.client.list_sensors()
        except Exception as e:
            self._log(f"Sensor list error: {e}"); return
        self.sensors = {s["id"]: s for s in sensors}
        self._log(f"Found {len(self.sensors)} sensors. Fetching 24 h samples…")
        threading.Thread(target=self._fetch_and_display, daemon=True).start()

    def _fetch_and_display(self):
        try:
            samples = self.client.samples_last_24h()
        except Exception as e:
            self._log(f"Sample fetch error: {e}"); return
        self._log(f"Total samples fetched: {len(samples)}")
        # group samples per sensor for later graph display
        self.samples_by_sensor.clear()
        for s in samples:
            sid = s["sensor"]
            t = s.get("temperature")
            # Try multiple timestamp field names to be API-shape agnostic
            ts_str = (
                s.get("observed")
                or s.get("timestamp")
                or s.get("time")
                or s.get("date")
            )
            if ts_str and t is not None:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    self.samples_by_sensor.setdefault(sid, []).append((ts, t))
                except Exception:
                    pass
        # compute percent <64
        stats: Dict[str, Dict[str, float]] = {}
        for s in samples:
            sid = s["sensor"]; t = s.get("temperature")
            if t is None: continue
            st = stats.setdefault(sid, {"count": 0, "below": 0})
            st["count"] += 1
            if t < 64:
                st["below"] += 1
        # Update layout directly since the sensor table was removed
        self.after(0, self._update_layout, stats)
        self.after(0, self._hide_loading)

    def _pct_to_color(self, pct: float) -> str:
        """Return a hex color from green->yellow->red for 0..100 percent."""
        pct = max(0.0, min(100.0, pct))
        if pct <= 50.0:
            # 0% -> green (#00ff00), 50% -> yellow (#ffff00)
            r = int((pct / 50.0) * 255)
            g = 255
        else:
            # 50% -> yellow (#ffff00), 100% -> red (#ff0000)
            r = 255
            g = int((1 - (pct - 50.0) / 50.0) * 255)
        return f"#{r:02x}{g:02x}00"

    def _update_layout(self, stats: Dict[str, Dict]):
        if not self.canvas or not self.layout_img:
            return
        self.canvas.delete("sensor_box")
        width = self.layout_img.width()
        height = self.layout_img.height()
        cols = max(1, int(width / 150))
        i = 0
        for sid, st in stats.items():
            name = self.sensors.get(sid, {}).get("name", sid)
            pct = (st["below"] / st["count"] * 100) if st["count"] else 0
            if name in self.sensor_positions:
                x, y = self.sensor_positions[name]
            else:
                row, col = divmod(i, cols)
                x = 20 + col * 150
                y = 20 + row * 70
            i += 1
            color = self._pct_to_color(pct)
            tags = ("sensor_box", sid)
            self.canvas.create_rectangle(
                x, y, x + 100, y + 40, fill=color, tags=tags
            )
            self.canvas.create_text(
                x + 50, y + 12, text=name, tags=tags
            )
            self.canvas.create_text(
                x + 50, y + 28, text=f"{pct:.1f}%", tags=tags
            )

    def _on_sensor_double(self, event: tk.Event):
        """Open a window with a temperature line graph for the clicked sensor."""
        if not self.canvas:
            return
        item = self.canvas.find_withtag("current")
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        sid = None
        for t in tags:
            if t != "sensor_box":
                sid = t
                break
        if sid:
            self._show_graph_window(sid)

    def _show_graph_window(self, sensor_id: str):
        data = self.samples_by_sensor.get(sensor_id)
        if not data:
            messagebox.showinfo("No Data", "No samples available for this sensor")
            return
        name = self.sensors.get(sensor_id, {}).get("name", sensor_id)
        win = tk.Toplevel(self)
        win.title(f"{name} – last 24h")
        fig = self.Figure(figsize=(6, 3), dpi=100)
        ax = fig.add_subplot(111)
        data_sorted = sorted(data, key=lambda p: p[0])
        times = [p[0] for p in data_sorted]
        temps = [p[1] for p in data_sorted]
        ax.plot(times, temps, marker="o", linestyle="-")
        ax.set_ylim(49, 76)
        ax.set_xlabel("Time")
        ax.set_ylabel("Temp (°F)")
        fig.autofmt_xdate()
        canvas = self.FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


# ==================== main ==================== #
if __name__ == "__main__":
    try:
        SensorPushGUI().mainloop()
    except Exception as ex:
        logger.exception("Unhandled exception: %s", ex)
