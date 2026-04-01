# Coil Array Interface Validation (Revised for Current Components)

This revision updates the interface validation so it matches the **current KiCad design** in:

- `hardware/kicad/CoilArrayBlock/CoilArrayBlock.kicad_sch`
- `hardware/kicad/CoilArrayBlock/CoilArrayBlock.kicad_pcb`

## Current Component Set (Validated)

- Current transformer: `U1 = CT-0705-HA`
- Instrumentation amplifier: `U2 = AD8422ARMZ`
- Gain resistor: `R3 = 1.05 kOhm` (AD8422 gain set)
- Output filter: `R4 = 2.0 kOhm`, `C5 = 10 nF`
- Burden/conditioning resistors: `R1 = 5 kOhm`, `R2 = 5 kOhm`
- Decoupling capacitors: `C1/C2 = 0.1 uF`, `C3/C4 = 10 uF`
- Connectors: `J1/J2/J3 = JST B2B-XH-A`

## Interface Definitions

### `Env_array_magfield` (Input)

- Magnetic flux nominal working range: **0.066 uT to 2.62 uT**
- Source condition (from your original validation assumptions): cable current around **1 A to 4 A**, distance up to **3 m**

### `Pwr_array_dcpwr` (Input, `J2`)

- Rail name: `VCC`
- Recommended operating range: **4.75 V to 5.25 V**

### `Pwr_array_vref` (Input, `J1`)

- Rail name: `Vref`
- Nominal value: **2.5 V** (bias/reference from the power conditioning block)

### `Array_sigproc_asig` (Output, `J3`)

- Signal name: `Vout`
- Output is biased around `Vref` (2.5 V nominal)
- Expected AC signal envelope (from your test plan): **0.5 mV to 250 mV**
  - Unit corrected from previous draft (`mA` typo -> `mV`)
- AD8422 gain from current parts:
  - `G = 1 + (19.8 kOhm / R3) = 1 + (19.8 kOhm / 1.05 kOhm) = 19.86 V/V`
- Output low-pass from current parts:
  - `f_c = 1 / (2*pi*R4*C5) = 1 / (2*pi*2000*10 nF) = 7.96 kHz`

## What Changed From the Previous Interface Section

- Corrected output magnitude units to **mV**.
- Updated filter limit to match actual schematic values (`R4 = 2 kOhm`, `C5 = 10 nF`).
- Aligned interface text with present connectors/rails (`VCC`, `Vref`, `Vout`).
- Removed references to components that are not in this Coil Array block schematic.

## Verification Command

Run from repo root:

```bash
python3 scripts/validate_interface.py
```

This confirms:

- Required labels (`VCC`, `Vref`, `Vout`) exist
- Required components and values are present
- Schematic and PCB references match
- Derived gain and cutoff match the current design
