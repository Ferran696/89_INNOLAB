"""Non-billable, per-recipe price scenario calculator."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid {label}: {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label} must be a finite non-negative amount")
    return result


def load_recipes(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as recipe_file:
        rows = list(csv.DictReader(recipe_file))
    recipes: dict[str, dict[str, str]] = {}
    for row in rows:
        recipe_id = row.get("recipe_id", "").strip()
        if not recipe_id:
            raise ValueError("Every recipe row must have a recipe_id")
        if recipe_id in recipes:
            raise ValueError(f"Duplicate recipe_id: {recipe_id}")
        recipes[recipe_id] = row
    return recipes


def calculate_quote(
    recipes: dict[str, dict[str, str]],
    units_by_recipe: dict[str, int],
    fixed_fee: Decimal = Decimal("0"),
    approved_extras: dict[str, Decimal] | None = None,
    rate_overrides: dict[str, Decimal] | None = None,
) -> dict[str, Any]:
    """Calculate an explicitly non-billable scenario from declared inputs only."""
    approved_extras = approved_extras or {}
    rate_overrides = rate_overrides or {}
    fixed_fee = _money(_decimal(fixed_fee, "fixed fee"))

    unknown_ids = (set(units_by_recipe) | set(rate_overrides)) - set(recipes)
    if unknown_ids:
        raise ValueError(f"Unknown recipe_id(s): {', '.join(sorted(unknown_ids))}")

    product_lines: list[dict[str, Any]] = []
    products_total = Decimal("0")
    for recipe_id, units in sorted(units_by_recipe.items()):
        if not isinstance(units, int) or units < 0:
            raise ValueError(f"Units for {recipe_id} must be a non-negative integer")
        if units == 0:
            continue
        recipe = recipes[recipe_id]
        rate_input = rate_overrides.get(recipe_id)
        rate_source = "manual_run_override" if rate_input is not None else "recipes.csv"
        if rate_input is None:
            raw_rate = recipe.get("illustrative_rate_eur_per_unit", "").strip()
            if not raw_rate:
                raise ValueError(
                    f"No illustrative rate for {recipe_id}; provide it explicitly, "
                    "do not infer it from nominal mass"
                )
            rate_input = _decimal(raw_rate, f"rate for {recipe_id}")
        rate = _decimal(rate_input, f"rate for {recipe_id}")
        line_total = _money(rate * units)
        products_total += line_total
        product_lines.append(
            {
                "recipe_id": recipe_id,
                "description": recipe.get("description", ""),
                "nominal_mass_g_declared": recipe.get("nominal_mass_g", ""),
                "units": units,
                "rate_eur_per_unit": str(rate),
                "rate_source": rate_source,
                "line_total_eur": str(line_total),
            }
        )

    extra_lines: list[dict[str, str]] = []
    extras_total = Decimal("0")
    for label, amount_input in sorted(approved_extras.items()):
        if not label.strip():
            raise ValueError("Extra line descriptions cannot be empty")
        amount = _money(_decimal(amount_input, f"extra {label}"))
        extras_total += amount
        extra_lines.append({"description": label.strip(), "amount_eur": str(amount)})

    total = fixed_fee + products_total + extras_total
    return {
        "scenario_type": "simulated_non_billable",
        "invoice_eligible": False,
        "currency": "EUR",
        "fixed_fee_eur": str(fixed_fee),
        "products": product_lines,
        "products_total_eur": str(_money(products_total)),
        "approved_extras": extra_lines,
        "extras_total_eur": str(_money(extras_total)),
        "total_eur": str(_money(total)),
        "note": (
            "Exemple il·lustratiu no facturable. Tarifes introduïdes explícitament; "
            "no s'infereixen del pes i no validen una oferta comercial."
        ),
    }


def _assignment(raw: str, label: str) -> tuple[str, str]:
    key, separator, value = raw.partition("=")
    if not separator or not key.strip() or not value.strip():
        raise ValueError(f"{label} must use NAME=VALUE")
    return key.strip(), value.strip()


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    default_recipes = Path(__file__).resolve().parents[1] / "config" / "recipes.csv"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipes", type=Path, default=default_recipes)
    parser.add_argument("--fixed-fee", default="0", help="explicit scenario amount in EUR")
    parser.add_argument(
        "--units",
        action="append",
        default=[],
        metavar="RECIPE_ID=COUNT",
        help="recipe quantity; repeat once per reference",
    )
    parser.add_argument(
        "--rate-eur-per-unit",
        action="append",
        default=[],
        metavar="RECIPE_ID=EUR",
        help="manual illustrative override for a missing CSV rate",
    )
    parser.add_argument(
        "--approved-extra",
        action="append",
        default=[],
        metavar="DESCRIPTION=EUR",
        help="explicit illustrative extra; repeat as needed",
    )
    parser.add_argument("--output", type=Path, help="optional local JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        units: dict[str, int] = {}
        for item in args.units:
            recipe_id, raw_units = _assignment(item, "--units")
            if recipe_id in units:
                raise ValueError(f"Duplicate units input for {recipe_id}")
            try:
                units[recipe_id] = int(raw_units)
            except ValueError as exc:
                raise ValueError(f"Unit count for {recipe_id} must be an integer") from exc

        rates: dict[str, Decimal] = {}
        for item in args.rate_eur_per_unit:
            recipe_id, raw_rate = _assignment(item, "--rate-eur-per-unit")
            if recipe_id in rates:
                raise ValueError(f"Duplicate rate override for {recipe_id}")
            rates[recipe_id] = _decimal(raw_rate, f"rate for {recipe_id}")

        extras: dict[str, Decimal] = {}
        for item in args.approved_extra:
            description, raw_amount = _assignment(item, "--approved-extra")
            if description in extras:
                raise ValueError(f"Duplicate extra description: {description}")
            extras[description] = _decimal(raw_amount, f"extra {description}")

        result = calculate_quote(
            load_recipes(args.recipes),
            units,
            _decimal(args.fixed_fee, "fixed fee"),
            extras,
            rates,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Simulated, non-billable quote written to {args.output}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())