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
        self.geometry("760x620")
        self.client: Optional[SensorPushClient] = None
        self.sensors: Dict[str, Dict] = {}
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

        cols = ("name", "count", "pct64")
        headers = ["Sensor", "Samples", "% < 64 °F"]
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        for col, hdr in zip(cols, headers):
            self.tree.heading(col, text=hdr)
            self.tree.column(col, anchor="center", width=140)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        logf = ttk.LabelFrame(self, text="Debug Log – each reading")
        logf.pack(fill="both", expand=False, padx=10, pady=(0, 10))
        self.log = tk.Text(logf, height=14, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)

    # ---- helpers ---- #
    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
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
        self.after(0, self._update_table, stats)

    def _update_table(self, stats: Dict[str, Dict]):
        self.tree.delete(*self.tree.get_children())
        for sid, st in stats.items():
            pct = (st["below"] / st["count"] * 100) if st["count"] else 0
            vals = (
                self.sensors.get(sid, {}).get("name", sid),
                st["count"],
                f"{pct:.1f}%",
            )
            self.tree.insert("", "end", iid=sid, values=vals)


# ==================== main ==================== #
if __name__ == "__main__":
    try:
        SensorPushGUI().mainloop()
    except Exception as ex:
        logger.exception("Unhandled exception: %s", ex)
