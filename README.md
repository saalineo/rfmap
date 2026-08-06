# Wavey

![Wavey](assets/wavey.png)

Real-time 3D Wi-Fi signal heatmapper with rogue AP detection and physical localization. Walk around, click your position, and watch the heatmap build like a live thermal camera.

[![Python](https://img.shields.io/badge/python-3.13+-blue?logo=python&logoColor=white)]()
[![PyQt6](https://img.shields.io/badge/PyQt6-6.x-green?logo=qt&logoColor=white)]()
[![VisPy](https://img.shields.io/badge/VisPy-0.16+-orange)]()
[![NumPy](https://img.shields.io/badge/NumPy-2.x-013243?logo=numpy&logoColor=white)]()
[![SciPy](https://img.shields.io/badge/SciPy-1.x-8CAAE6?logo=scipy&logoColor=white)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macos-lightgrey)]()
[![OpenGL](https://img.shields.io/badge/GPU-OpenGL-red?logo=opengl&logoColor=white)]()
[![Status](https://img.shields.io/badge/status-active-success)]()

## Features

### 3D Heatmapper
- **3D OpenGL heatmap** — GPU-accelerated Phong-shaded surface via VisPy
- **Auto router detection** — signal-weighted centroid from your clicks
- **Connected device mapping** — live device names + positions around the router
- **Real-time RSSI** — last point updates automatically when signal changes
- **Wall drawing** — drag to add drywall, brick, or concrete obstacles
- **Scrolling waterfall** — live RSSI history overlay
- **Turntable camera** — arrow keys rotate the 3D view
- **Tokyo Night theme** — dark UI throughout

### Threat Scanner
Toggle the **Threat Scanner** panel to access the AP scanner and rogue AP localization tool:
- **AP Scanner** — enumerate all nearby networks (SSID, BSSID, channel, security, RSSI)
- **Rogue Detector** — whitelist-based heuristics flag evil twins, open corporate SSIDs, hidden APs
- **Survey Mode** — click floor points around a target AP to collect RSSI samples
- **Localization Engine** — nonlinear least-squares fit with error ellipse and GDOP
- **3D Threat Overlay** — red ceiling marker, confidence ellipse, drop line on the 3D canvas
- **Reporting** — export survey sessions as JSON/CSV/HTML reports

## Quick Start

```bash
python main.py
```

## Usage

| Action | Result |
|---|---|
| Click on floor | Record signal measurement |
| Click-drag | Draw a wall |
| Arrow keys | Rotate camera |
| Auto-sample checkbox | Auto-record every 1s |
| Demo Data button | 20 synthetic points instantly |
| ⚡ Threat Scanner | Open AP scanner + rogue AP survey |

## Architecture

Three decoupled pipelines on separate threads:

1. **Wi-Fi** (`wifi/networking.py`) — OS-level RSSI polling with automatic simulated fallback
2. **Heatmap** (`heatmap/`) — Gaussian blob kernel regression, physics path-loss model, router estimation
3. **UI** (`ui/`) — PyQt6 window with VisPy OpenGL 3D canvas

## Platform Support

| OS | Method | Permissions |
|---|---|---|
| Linux | `/proc/net/wireless`, `iw`, `iwconfig` | None needed |
| Windows | `netsh wlan show interfaces` | None needed |
| macOS | `airport -I` | May be missing on Ventura+ |

## Calibration

Edit `heatmap/math.py`:

- **CELL_METERS** (default 0.3): real-world meters per grid cell
- **TX_POWER_DBM** (default -30.0): RSSI at 1 cell from router

