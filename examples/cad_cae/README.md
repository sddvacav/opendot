# Geometry-only beam recipe

`beam.parameters.json` contains synthetic dimensions in **meters**. The optional
build123d adapter converts once to millimeters and explicitly exports STEP in mm.
Default dimensions are 200 × 20 × 3 mm, volume 12,000 mm³ = 0.000012 m³.

From a checkout in a separate CAD environment with build123d 0.10.0 installed:

```sh
PYTHONPATH=src python -m opendot_engineering.executors.geometry \
  /tmp/opendot-geometry-example --cadquery-compatibility
```

The optional compatibility flag additionally requires CadQuery; omit it for a
build123d-only run. Choose a new directory outside the repository. Existing
directories, including empty ones, are refused. No generated STEP, receipts,
dependency wheels, or native binaries belong in this source directory.

Programmatic parameters:

```python
import json
from pathlib import Path
from opendot_engineering.executors.geometry import export_beam

parameters = json.loads(Path("examples/cad_cae/beam.parameters.json").read_text())
receipt = export_beam(parameters, Path("/tmp/opendot-geometry-programmatic"))
```

This is a deterministic geometry recipe and STEP compatibility check. No mesh,
FEA, physical test, material choice, strength claim or scientific acceptance is
included. See [the geometry contract](../../docs/cad-geometry.md).
