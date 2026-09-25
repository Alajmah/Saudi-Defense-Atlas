#!/usr/bin/env python3
"""Validate SDA JSON Schemas and their positive/negative fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "v0.1"
FIXTURE_FILE = ROOT / "tests" / "fixtures" / "schema-fixtures.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_registry() -> tuple[dict[str, dict], Registry]:
    schemas: dict[str, dict] = {}
    registry = Registry()

    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = load_json(path)
        Draft202012Validator.check_schema(schema)

        schema_id = schema.get("$id")
        if not schema_id:
            raise ValueError(f"{path}: missing $id")

        schemas[path.name] = schema
        registry = registry.with_resource(schema_id, Resource.from_contents(schema))

    return schemas, registry


def validate_fixtures(schemas: dict[str, dict], registry: Registry) -> list[str]:
    fixture_doc = load_json(FIXTURE_FILE)
    failures: list[str] = []

    for expected_valid, group_name in ((True, "valid"), (False, "invalid")):
        for case in fixture_doc.get(group_name, []):
            name = case["name"]
            schema_name = case["schema"]
            instance = case["instance"]

            if schema_name not in schemas:
                failures.append(f"{name}: unknown schema {schema_name}")
                continue

            validator = Draft202012Validator(
                schemas[schema_name],
                registry=registry,
                format_checker=FormatChecker(),
            )
            errors = sorted(
                validator.iter_errors(instance),
                key=lambda error: tuple(str(segment) for segment in error.absolute_path),
            )

            if expected_valid and errors:
                rendered = "; ".join(
                    f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
                    for error in errors
                )
                failures.append(f"{name}: expected valid, got {rendered}")
            elif not expected_valid and not errors:
                failures.append(f"{name}: expected invalid, but validation passed")

    return failures


def main() -> int:
    try:
        schemas, registry = build_registry()
        failures = validate_fixtures(schemas, registry)
    except Exception as exc:  # noqa: BLE001 - CLI should surface any validation setup failure.
        print(f"schema validation setup failed: {exc}", file=sys.stderr)
        return 2

    if failures:
        print("Schema fixture validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Validated {len(schemas)} schemas and all fixture expectations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
