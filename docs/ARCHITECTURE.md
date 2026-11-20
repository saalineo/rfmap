# RFMap architecture

## Product purpose

RFMap is a desktop Wi-Fi site-survey application. A user imports a floor plan, sets its scale, records signal measurements while moving through a space, and reviews coverage as a heatmap. The optional assessment panel inventories nearby access points and helps an authorized operator compare them against an allowlist.

RFMap is not an attack tool. It does not transmit frames, break Wi-Fi security, or treat RSSI-only location estimates as certain. All security assessment must be authorized by the network owner.

## Repository map

```text
main.py       Application composition: Qt event loop, window, RSSI worker
wifi/         Connected-network RSSI, SSID, adapter, and client discovery
heatmap/      Grid geometry, wall attenuation, interpolation, colour mapping
security/     AP scans, allowlist rules, localization, sessions, audit events
ui/           PyQt widgets and VisPy 3D rendering
tests/        Unit, flow, parser, and regression tests
docs/         Architecture and contributor documentation
```

## Runtime flow

```text
Wi-Fi adapter ──> wifi.RSSIWorker ──> MainWindow ──> HeatmapWorker ──> HeatmapCanvas
                                          │
                                          ├── recorded survey points
                                          └── APScanner ──> SentinelPanel / selected AP
```

`main.py` owns application startup. It creates one `MainWindow` and one `RSSIWorker`, then connects Qt signals to the window. The window owns the AP scanner and heatmap worker because it owns the survey state they consume.

## Primary data contracts

| Type | Producer | Consumer | Meaning |
|---|---|---|---|
| `float` RSSI in dBm | `RSSIWorker`, AP scanners | `MainWindow` | A live signal reading; never silently simulated |
| `(x, y, rssi)` | `MainWindow` | `HeatmapWorker` | One measurement in grid coordinates |
| `APObservation` | `APScanner` | UI, detector, localizer | A nearby AP found in a scan |
| `SurveySample` | Survey-mode click | `APLocalizer`, session export | RSSI sample for an explicitly selected AP |
| `LocalizationFix` | `APLocalizer` | 3D overlay, report | Estimate with uncertainty; not a guarantee |

Grid coordinates run from `0` through `GRID_SIZE - 1`. The map-scale control converts cells to metres for the path-loss model; changing it must be passed into heatmap calculation rather than only changing a label.

## Non-negotiable behavior

- A missing Wi-Fi adapter or failed scan must show setup guidance, not synthetic data.
- Demo data is only created by an explicit user action and stays visibly labelled until cleared.
- Linux scans must not run `sudo` from the GUI. Prefer NetworkManager (`nmcli`), then attempt unprivileged `iw`.
- Keep real-time I/O and heatmap computation off the GUI thread.
- Treat rogue-AP classifications and physical locations as heuristics with uncertainty.

## Where changes belong

| Change | Primary location |
|---|---|
| New OS adapter/source support | `wifi/networking.py` and `security/ap_scanner.py` |
| Signal or wall model change | `heatmap/math.py`, with a regression test |
| Heatmap interpolation/presentation change | `heatmap/heatmap.py` or `ui/canvas.py` |
| Survey interaction or controls | `ui/main_window.py` |
| Scanner-table, whitelist, or export UI | `ui/scanner_panel.py` and `security/` |
| Report/session format | `security/sessions.py` |

See [Development](DEVELOPMENT.md) for the normal edit-and-test workflow.
