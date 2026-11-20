# `heatmap/` — coverage model

This package turns survey points into the signal surface rendered by RFMap.

| File | Responsibility |
|---|---|
| `math.py` | Grid constants, obstacles, path-loss baseline, router estimate, geometry helpers |
| `heatmap.py` | Gaussian interpolation and blend with the physics baseline |
| `colormap.py` | Signal-strength colours used by the canvas |

Coordinates are grid cells, while path loss is calculated in metres using `cell_meters`. Preserve that distinction when changing the model. Wall attenuation is approximate and should be validated with calculation tests rather than visual inspection alone.
