# `tests/` — behavior protection

The test suite uses the standard library `unittest` runner.

| Test area | Files |
|---|---|
| Scanner parsing and calibration | `test_scanner.py` |
| Detection and allowlist rules | `test_detection.py`, `test_edge_cases.py` |
| Survey/localization model | `test_survey_flow.py`, `test_localization.py`, `test_particle_filter.py` |
| Overlay, sessions, and full flows | `test_overlay_geometry.py`, `test_storage.py`, `test_e2e.py` |
| Sentry/deauth logic | `test_sentry.py` |

Run all tests with:

```bash
python -m unittest discover -s tests -q
```

Keep parser fixtures and simulated scanner data inside tests or explicit demos. Production runtime must not silently switch to either.
