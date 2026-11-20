# Developing RFMap

## Setup

RFMap targets Python 3.13 or newer. Install the declared dependencies in an isolated environment, then run the application:

```bash
python -m pip install -r requirements.txt
python main.py
```

For Linux AP scans, enable NetworkManager and ensure `nmcli` can see the chosen Wi-Fi adapter. RFMap deliberately does not prompt for `sudo`.

## Everyday checks

```bash
python -m unittest discover -s tests -q
python -m compileall -q main.py wifi heatmap security ui tests
```

Use the UI manually after dependency installation to check floor-plan import, scale changes, adapter selection, live scan failure guidance, and the demo-data warning.

## Safe feature workflow

1. Read the relevant package README and identify the data contract being changed.
2. Keep hardware I/O and expensive calculation in workers; send results to the UI with Qt signals.
3. Add a narrow regression test for new parsing, calculation, or classification logic.
4. Keep demo and real data separate. A survey point must state which source supplied its RSSI.
5. Update the closest README when the behavior or extension point changes.

## Testing without radio hardware

- Set `SENTINEL_SCANNER` to an `iw`-format fixture when exercising parser and scan flows.
- Use the explicit **Load DEMO Data** control only for a visual heatmap demonstration.
- Do not change the runtime code to make tests pass by silently enabling simulation.

## Common pitfalls

- RSSI values fluctuate and should not be treated as exact distance measurements.
- `nmcli` signal percentages are converted to approximate dBm; document source-specific limitations in the UI.
- A selected AP's RSSI comes from recent scans, while the connected-network RSSI is polled continuously. Do not overwrite one with the other.
- VisPy and OpenGL need a working desktop graphics environment; headless test environments can still run the non-UI suite.
