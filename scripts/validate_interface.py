#!/usr/bin/env python3
"""Validate Coil Array interface assumptions against current KiCad components."""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path


EXPECTED_COMPONENTS = {
    "U1": {"lib_id": "CT:CT-0705-HA"},
    "U2": {"lib_id": "AD8422:AD8422ARMZ", "value": "AD8422ARMZ"},
    "J1": {"lib_id": "B2B-XH-A:B2B-XH-A", "value": "B2B-XH-A"},
    "J2": {"lib_id": "B2B-XH-A:B2B-XH-A", "value": "B2B-XH-A"},
    "J3": {"lib_id": "B2B-XH-A:B2B-XH-A", "value": "B2B-XH-A"},
    "R1": {"value": "5k"},
    "R2": {"value": "5k"},
    "R3": {"value": "1.05k"},
    "R4": {"value": "2000"},
    "C1": {"value": "0.1uF"},
    "C2": {"value": "0.1uF"},
    "C3": {"value": "10uF"},
    "C4": {"value": "10uF"},
    "C5": {"value": "10nF"},
}

REQUIRED_GLOBAL_LABELS = {"VCC", "Vref", "Vout"}

# KiCad parser

def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "()":
            tokens.append(ch)
            i += 1
            continue
        if ch == '"':
            i += 1
            value: list[str] = []
            while i < n:
                cur = text[i]
                if cur == '"':
                    i += 1
                    break
                if cur == "\\" and i + 1 < n:
                    value.append(text[i + 1])
                    i += 2
                    continue
                value.append(cur)
                i += 1
            tokens.append("".join(value))
            continue

        start = i
        while i < n and (not text[i].isspace()) and text[i] not in "()":
            i += 1
        tokens.append(text[start:i])
    return tokens


def parse_sexpr(text: str):
    tokens = tokenize(text)
    idx = 0

    def parse_one():
        nonlocal idx
        if idx >= len(tokens):
            raise ValueError("Unexpected end of input")

        tok = tokens[idx]
        idx += 1

        if tok == "(":
            out = []
            while idx < len(tokens) and tokens[idx] != ")":
                out.append(parse_one())
            if idx >= len(tokens):
                raise ValueError("Missing closing parenthesis")
            idx += 1
            return out

        if tok == ")":
            raise ValueError("Unexpected closing parenthesis")

        return tok

    exprs = []
    while idx < len(tokens):
        exprs.append(parse_one())

    if len(exprs) != 1:
        raise ValueError("Expected exactly one top-level expression")

    return exprs[0]


def child_value(node, key: str):
    for child in node[1:]:
        if isinstance(child, list) and child and child[0] == key:
            if len(child) > 1:
                return child[1]
            return None
    return None


def properties(node) -> dict[str, str]:
    out: dict[str, str] = {}
    for child in node[1:]:
        if isinstance(child, list) and len(child) >= 3 and child[0] == "property":
            out[str(child[1])] = str(child[2])
    return out


def read_schematic(path: Path):
    root = parse_sexpr(path.read_text(encoding="utf-8"))
    if not (isinstance(root, list) and root and root[0] == "kicad_sch"):
        raise ValueError(f"{path} is not a KiCad schematic")

    comps: dict[str, dict[str, str]] = {}
    labels: set[str] = set()

    for item in root[1:]:
        if not isinstance(item, list) or not item:
            continue

        key = item[0]
        if key == "global_label" and len(item) > 1:
            labels.add(str(item[1]))
            continue

        if key != "symbol":
            continue

        lib_id = child_value(item, "lib_id")
        if not lib_id:
            continue

        props = properties(item)
        ref = props.get("Reference", "")
        if not ref or ref.startswith("#"):
            continue

        comps[ref] = {
            "lib_id": str(lib_id),
            "value": props.get("Value", ""),
            "footprint": props.get("Footprint", ""),
        }

    return comps, labels


def read_pcb(path: Path):
    root = parse_sexpr(path.read_text(encoding="utf-8"))
    if not (isinstance(root, list) and root and root[0] == "kicad_pcb"):
        raise ValueError(f"{path} is not a KiCad PCB")

    comps: dict[str, dict[str, str]] = {}
    for item in root[1:]:
        if not isinstance(item, list) or not item or item[0] != "footprint":
            continue

        fp_name = str(item[1]) if len(item) > 1 else ""
        props = properties(item)
        ref = props.get("Reference", "")

        if not ref or ref.startswith("#") or ref == "G***":
            continue

        comps[ref] = {
            "footprint": fp_name,
            "value": props.get("Value", ""),
        }

    return comps


# Value parsing

def normalize_unit(unit: str) -> str:
    return (
        unit.replace("Ω", "")
        .replace("ω", "")
        .replace("μ", "u")
        .replace("µ", "u")
        .replace("ohms", "")
        .replace("ohm", "")
        .strip()
        .lower()
    )


def parse_value(raw: str, kind: str) -> float:
    txt = raw.strip()
    match = re.match(r"^([+-]?\d*\.?\d+)\s*([a-zA-ZuµμΩω]*)$", txt)
    if not match:
        raise ValueError(f"Could not parse {kind} value '{raw}'")

    magnitude = float(match.group(1))
    unit = normalize_unit(match.group(2))

    if kind == "resistor":
        mult = {
            "": 1.0,
            "r": 1.0,
            "k": 1e3,
            "m": 1e6,
        }.get(unit)
        if mult is None:
            raise ValueError(f"Unsupported resistor unit '{unit}' in '{raw}'")
        return magnitude * mult

    if kind == "capacitor":
        mult = {
            "": 1.0,
            "f": 1.0,
            "mf": 1e-3,
            "uf": 1e-6,
            "nf": 1e-9,
            "pf": 1e-12,
        }.get(unit)
        if mult is None:
            raise ValueError(f"Unsupported capacitor unit '{unit}' in '{raw}'")
        return magnitude * mult

    raise ValueError(f"Unknown kind '{kind}'")


def parse_expected_value(reference: str, value: str) -> float:
    kind = "resistor" if reference.startswith("R") else "capacitor"
    return parse_value(value, kind)


def compare_component_values(reference: str, actual: str, expected: str) -> bool:
    if reference.startswith(("R", "C")):
        actual_num = parse_expected_value(reference, actual)
        expected_num = parse_expected_value(reference, expected)
        return math.isclose(actual_num, expected_num, rel_tol=1e-6, abs_tol=1e-12)

    return actual.strip() == expected.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schematic",
        default="hardware/kicad/CoilArrayBlock/CoilArrayBlock.kicad_sch",
        help="Path to the KiCad schematic file",
    )
    parser.add_argument(
        "--pcb",
        default="hardware/kicad/CoilArrayBlock/CoilArrayBlock.kicad_pcb",
        help="Path to the KiCad PCB file",
    )
    args = parser.parse_args()

    schematic_path = Path(args.schematic)
    pcb_path = Path(args.pcb)

    if not schematic_path.exists():
        print(f"ERROR: schematic not found: {schematic_path}")
        return 2
    if not pcb_path.exists():
        print(f"ERROR: pcb not found: {pcb_path}")
        return 2

    schematic_components, global_labels = read_schematic(schematic_path)
    pcb_components = read_pcb(pcb_path)

    failures: list[str] = []
    warnings: list[str] = []

    for label in sorted(REQUIRED_GLOBAL_LABELS):
        if label not in global_labels:
            failures.append(f"Missing required global label: {label}")

    for ref, rules in EXPECTED_COMPONENTS.items():
        comp = schematic_components.get(ref)
        if comp is None:
            failures.append(f"Missing expected schematic component: {ref}")
            continue

        expected_lib = rules.get("lib_id")
        if expected_lib and comp.get("lib_id") != expected_lib:
            failures.append(
                f"{ref} lib_id mismatch: expected '{expected_lib}', got '{comp.get('lib_id')}'"
            )

        expected_val = rules.get("value")
        if expected_val:
            try:
                matches = compare_component_values(ref, comp.get("value", ""), expected_val)
            except ValueError as exc:
                failures.append(f"{ref} value parse error: {exc}")
                matches = True
            if not matches:
                failures.append(
                    f"{ref} value mismatch: expected '{expected_val}', got '{comp.get('value')}'"
                )

    schematic_refs = {r for r in schematic_components if not r.startswith("#")}
    pcb_refs = set(pcb_components)

    missing_on_pcb = sorted(schematic_refs - pcb_refs)
    extra_on_pcb = sorted(pcb_refs - schematic_refs)

    if missing_on_pcb:
        failures.append("References in schematic but missing in PCB: " + ", ".join(missing_on_pcb))
    if extra_on_pcb:
        warnings.append("References in PCB but not in schematic: " + ", ".join(extra_on_pcb))

    # Derived interface numbers from current component values.
    try:
        rg_ohm = parse_value(schematic_components["R3"]["value"], "resistor")
        gain = 1.0 + (19800.0 / rg_ohm)
    except Exception as exc:
        failures.append(f"Could not derive AD8422 gain from R3: {exc}")
        gain = float("nan")

    try:
        r4_ohm = parse_value(schematic_components["R4"]["value"], "resistor")
        c5_f = parse_value(schematic_components["C5"]["value"], "capacitor")
        cutoff_hz = 1.0 / (2.0 * math.pi * r4_ohm * c5_f)
    except Exception as exc:
        failures.append(f"Could not derive low-pass cutoff from R4/C5: {exc}")
        cutoff_hz = float("nan")

    if not math.isnan(gain) and not (18.0 <= gain <= 22.0):
        failures.append(f"AD8422 gain out of expected range (~20): computed {gain:.2f}")

    print("=== Coil Array Interface Validation ===")
    print(f"Schematic: {schematic_path}")
    print(f"PCB:       {pcb_path}")
    print("")

    print("Derived from current components:")
    if not math.isnan(gain):
        print(f"- AD8422 gain (from R3={schematic_components['R3']['value']}): {gain:.2f} V/V")
    if not math.isnan(cutoff_hz):
        print(
            "- Output RC low-pass cutoff "
            f"(R4={schematic_components['R4']['value']}, C5={schematic_components['C5']['value']}): "
            f"{cutoff_hz:.2f} Hz"
        )

    print("")

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
        print("")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS")
    print("All required interfaces/components match the current KiCad design.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
