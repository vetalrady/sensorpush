# SensorPush Temperature Dashboard

A lightweight Tkinter GUI that connects to your **SensorPush Cloud Gateway** account, downloads the last 24 hours of temperature readings for every sensor, and shows what **percentage of those samples were below 64 °F**. Each individual reading is echoed to an on‑screen debug log for full transparency.

---

## Features

| Feature                    | Description                                                                                |
| -------------------------- | ------------------------------------------------------------------------------------------ |
| **One‑click fetch**        | Enter your SensorPush dashboard credentials and hit **Fetch 24 h**.                        |
| **Temperature‑only focus** | Humidity & dew‑point data are ignored by design.                                           |
| **Per‑sensor stats**       | See total sample count and `% < 64 °F` for each sensor.                                    |
| **Verbose Debug Log**      | Every raw reading (sensor, timestamp, temp) plus raw JSON snippets are printed live.       |
| **API shape‑agnostic**     | Handles both legacy (`{"sensors": {…}}`) and modern (`{"samples": […]}`) response formats. |

---

## Screenshots

*(Add your own screenshots here)*

---

## Getting Started

### 1 . Prerequisites

* **Python ≥ 3.8**
* `pip install` the only third‑party dependency:

```bash
pip install requests
```

> **Linux users:** Install Tk if it’s missing:
>
> ```bash
> sudo apt-get install python3-tk
> ```

### 2 . Clone & Run

```bash
git clone <your‑repo‑url>
cd sensorpush‑temp‑dashboard
python sensorpush_gui.py          # or whatever filename you saved
```

### 3 . Login & Fetch

1. **Email / Password** – Same ones you use at [https://dashboard.sensorpush.com](https://dashboard.sensorpush.com).
2. Click **Fetch 24 h**.
3. Watch the table and Debug Log populate.

---

## Project Structure

```
├── sensorpush_gui.py   # Main application code (Tk + API client)
├── README.md           # You are here
└── requirements.txt    # (optional) just requests
```

---

## How It Works

1. **OAuth Login** – `/oauth/authorize` → `/oauth/accesstoken`
2. **List Sensors** – `/devices/sensors`
3. **Get Samples** – `/samples` with `startTime` & `endTime` (24 h window)
4. **Analytics** – Count and percentage of readings `< 64°F`.
5. **Display** – Tkinter `Treeview` for stats, `Text` widget for logs.

---

## Customisation Tips

* **Change the threshold** – Edit `if t < 64:` in `SensorPushGUI._fetch_and_display`.
* **Different time span** – Adjust the `start = end - timedelta(hours=24)` line.
* **CSV export** – The raw `samples` list is already available; write it to disk with the `csv` module.
* **Graphs** – Pipe the data into `matplotlib` or `plotly` for line charts.

---

## Troubleshooting

* **`Login failed`** – Double‑check credentials; 2FA is not supported.
* **`Sensor list error`** – Make sure your account actually has sensors and cloud access.
* **`Sample fetch error`** – Gateway offline or subscription expired? Verify connectivity in SensorPush dashboard.

Use the Debug Log: it prints raw JSON payloads and every reading, which helps pinpoint API quirks.

---

## License

MIT – do what you want, no warranty.

---

## Acknowledgements

* [SensorPush](https://www.sensorpush.com/) for their public cloud API.
* Tkinter – the classic Python GUI toolkit.
