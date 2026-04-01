# Coil Array Block

Coil-array magnetic-field sensing block designed and implemented by Jack Fraley.

This repository is prepared for sharing on GitHub and includes:

- KiCad source files for the board/schematic
- Gerber manufacturing outputs
- Revised interface validation aligned to the **current** components
- A repeatable validation script for schematic/PCB consistency

## Repository Layout

- `hardware/kicad/CoilArrayBlock/`
  - `CoilArrayBlock.kicad_sch`
  - `CoilArrayBlock.kicad_pcb`
  - `CoilArrayBlock.kicad_pro`
  - `CT-0705-HA-new.pretty/` (local footprint library)
  - `Gerber/` and `CoilArrayBlock-job.gbrjob`
- `docs/Interface-Validation-Revised.md`
- `scripts/validate_interface.py`

## Validation

Run:

```bash
python3 scripts/validate_interface.py
```

The script validates required interfaces/components and calculates derived values from current parts (instrumentation-amplifier gain and output RC cutoff).

## Notes

- Interface numbers in the revised document are updated to match the present schematic values.
- Output-amplitude units were corrected to `mV`.
