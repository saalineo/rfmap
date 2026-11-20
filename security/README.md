# `security/` — authorized AP assessment

This package scans access points and provides defensive assessment features. Use it only on networks you are authorized to assess.

| Area | Files |
|---|---|
| AP discovery | `ap_scanner.py` |
| Allowlist and classification | `allowlist.py`, `detection.py`, `sentry_engine.py` |
| RSSI survey localization | `localization.py`, `particle_filter.py`, `types.py` |
| Deauthentication event monitoring | `deauth_detector.py` |
| Session reports/configuration | `sessions.py`, `config.py`, `logging.py` |

`APObservation`, `SurveySample`, `RogueReport`, and `LocalizationFix` in `types.py` are the package's shared contracts. Keep detections explainable: every non-trusted classification needs a rule/reason and a confidence value. A localization result must retain its uncertainty metrics.

The scanner must return an empty result plus clear UI guidance when it cannot access the radio. Do not add automatic simulated scans to production flow.
