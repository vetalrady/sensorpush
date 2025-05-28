# SensorPush Temperature Dashboard

A lightweight Tkinter GUI that connects to your **SensorPush Cloud Gateway** account, downloads the last 24 hours of temperature readings for every sensor, and shows what **percentage of those samples were below 64 °F**.

---

## Features

| Feature                    | Description                                                                                |
| -------------------------- | ------------------------------------------------------------------------------------------ |
| **One‑click fetch**        | Enter your SensorPush dashboard credentials and hit **Fetch 24 h**.                        |
| **Temperature‑only focus** | Humidity & dew‑point data are ignored by design.                                           |
| **Per‑sensor stats**       | See total sample count and `% < 64 °F` for each sensor.                                    |
| **API shape‑agnostic**     | Handles both legacy (`{"sensors": {…}}`) and modern (`{"samples": […]}`) response formats. |
| **Layout overlay**         | Displays each sensor on `layout.png` with its `% < 64 °F` value. |

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
python sensorpush.py
```

Place your `layout.png` file in the same directory as `sensorpush.py` if you want to see the overlay feature.

### 3 . Login & Fetch

1. **Email / Password** – Same ones you use at [https://dashboard.sensorpush.com](https://dashboard.sensorpush.com).
2. Click **Fetch 24 h**.
3. Watch the layout overlay update.

---

## Project Structure

```
├── sensorpush.py       # Main application code (Tk + API client)
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
* **Layout positions** – Edit `sensor_positions` in `sensorpush.py` to place overlays on your `layout.png` using sensor **names** as the keys.

---

## Troubleshooting

* **`Login failed`** – Double‑check credentials; 2FA is not supported.
* **`Sensor list error`** – Make sure your account actually has sensors and cloud access.
* **`Sample fetch error`** – Gateway offline or subscription expired? Verify connectivity in SensorPush dashboard.


---

## License

MIT – do what you want, no warranty.

---

## Acknowledgements

* [SensorPush](https://www.sensorpush.com/) for their public cloud API.
* Tkinter – the classic Python GUI toolkit.
