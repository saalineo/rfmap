# RFMap architecture

## Product purpose

RFMap is a desktop Wi-Fi site-survey application. A user imports a floor plan, sets its scale, records signal measurements while moving through a space, and reviews coverage as a heatmap. The optional assessment panel inventories nearby access points and helps an authorized operator compare them against an allowlist.

RFMap is not an attack tool. It does not transmit frames, break Wi-Fi security, or treat RSSI-only location estimates as certain. All security assessment must be authorized by the network owner.

## Repository map

```text
rfmap/app.py          Application composition: Qt event loop, window, RSSI worker
rfmap/core/           Pure numerics, no Qt: constants, geometry, propagation, heatmap, colormap
rfmap/wifi/           Connected-network RSSI/SSID/clients (probes/ per OS, provider, worker)
rfmap/scanning/       AP discovery (backends/ per OS, parsing, simulated, worker)
rfmap/sentinel/       Rogue-AP detection, allowlist, trust score, deauth monitor, config
rfmap/localization/   Particle filter and AP localizer
rfmap/storage/        Session persistence and export
rfmap/ui/             PyQt6: main_window, survey/, assessment/, canvas/, chrome/, theme/, workers/
rfmap/models.py       Shared dataclasses (APObservation, SurveySample, ...)
rfmap/paths.py        Every on-disk location (config/, logs/, sessions/)
config/               Runtime JSON: sentinel.json, allowlist.json
scripts/              Manual tools (scan_smoke.py)
tests/                Unit, flow, parser, and regression tests
docs/         Architecture and contributor documentation
```

## Runtime flow

```text
Wi-Fi adapter ──> wifi.RSSIWorker ──> MainWindow ──> HeatmapWorker ──> HeatmapCanvas
                                          │
                                          ├── recorded survey points
                                          └── APScanner ──> SentinelPanel / selected AP
```

`rfmap/app.py` owns application startup. It creates one `MainWindow` and one `RSSIWorker`, then connects Qt signals to the window. The window owns the AP scanner and heatmap worker because it owns the survey state they consume.

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
| New OS adapter/source support | `rfmap/wifi/` and `rfmap/scanning/` |
| Signal or wall model change | `rfmap/core/propagation.py`, with a regression test |
| Heatmap interpolation/presentation change | `rfmap/core/heatmap.py` or `rfmap/ui/canvas/heatmap_canvas.py` |
| Survey interaction or controls | `rfmap/ui/main_window.py` |
| Scanner-table, whitelist, or export UI | `rfmap/ui/assessment/sentinel_panel.py` and `rfmap/sentinel/` |
| Report/session format | `rfmap/storage/sessions.py` |

See [Development](DEVELOPMENT.md) for the normal edit-and-test workflow.
