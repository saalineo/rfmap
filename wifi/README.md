# `wifi/` — connected-network telemetry

This package reads information about the Wi-Fi network the computer is currently using.

| File | Responsibility |
|---|---|
| `networking.py` | Platform-specific RSSI, SSID, adapter, and associated-device lookup; `RSSIWorker` thread |

## Contract

`RSSIWorker` emits `rssi_updated(rssi, source)`, `source_changed(description)`, `ssid_updated(ssid)`, and `devices_updated(names)`. It may retain a last known real reading briefly, but it must never invent one when hardware access fails.

Add a platform source behind `RSSIProvider`; preserve the adapter-selection API and return `None` when live data is unavailable. The UI is responsible for explaining that state to the operator.
