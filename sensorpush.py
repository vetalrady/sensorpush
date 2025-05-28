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
        self.layout_img: Optional[tk.PhotoImage] = None
        self.canvas: Optional[tk.Canvas] = None
        # Debug log widget removed; keep attribute for _log method
        self.log: Optional[tk.Text] = None
        # Positions on the layout image keyed **by sensor name**.
        # Add your own sensor names here with (x, y) coordinates.
        self.sensor_positions: Dict[str, tuple[int, int]] = {
            "1": (20, 20),
            "2": (170, 20),
        }
        self._build_ui()

    # ---- UI ---- #
    def _build_ui(self):
        lf = ttk.LabelFrame(self, text="Login")
        lf.pack(fill="x", padx=10, pady=5)
        ttk.Label(lf, text="Email:").grid(row=0, column=0, sticky="e", padx=5, pady=4)
        ttk.Label(lf, text="Password:").grid(row=1, column=0, sticky="e", padx=5, pady=4)
        self.email_var = tk.StringVar(); self.pwd_var = tk.StringVar()
        ttk.Entry(lf, textvariable=self.email_var, width=35).grid(row=0, column=1, padx=5, pady=4)
        ttk.Entry(lf, textvariable=self.pwd_var, show="*", width=35).grid(row=1, column=1, padx=5, pady=4)
        ttk.Button(lf, text="Fetch 24 h", command=self._on_fetch).grid(row=0, column=2, rowspan=2, padx=10)
        # Sensor list table and debug log removed for clean layout
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
    def _on_fetch(self):
        email, pwd = self.email_var.get().strip(), self.pwd_var.get().strip()
        if not email or not pwd:
            messagebox.showwarning("Missing", "Enter email & password"); return
        self._log("Logging in…")
        self.client = SensorPushClient(email, pwd)
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
        for s in samples:
            sid = s["sensor"]; name = self.sensors.get(sid, {}).get("name", sid)
            self._log(f"{name} @ {s.get('observed','?')} → {s.get('temperature','?')}°F")
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
            # Tkinter does not support RGBA hex colors. Using plain white.
            self.canvas.create_rectangle(
                x, y, x + 100, y + 40, fill="#ffffff", tags="sensor_box"
            )
            self.canvas.create_text(
                x + 50, y + 12, text=name, tags="sensor_box"
            )
            self.canvas.create_text(
                x + 50, y + 28, text=f"{pct:.1f}%", tags="sensor_box"
            )


# ==================== main ==================== #
if __name__ == "__main__":
    try:
        SensorPushGUI().mainloop()
    except Exception as ex:
        logger.exception("Unhandled exception: %s", ex)
