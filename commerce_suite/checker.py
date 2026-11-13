"""Cross-surface consistency checker.

Reads the three surfaces of one fixture store:

  * ``page.html``        - the product page: JSON-LD + a policies section
  * ``feed.csv``         - the product feed a shopping agent / aggregator ingests
  * ``structured.json``  - the standalone structured-data document

and compares, per product, the fields an AI shopping agent relies on:
price, currency, availability, identifier (SKU), and the store-level
shipping and returns policies. Every disagreement is reported as an exact
conflict: field, surface A and its value, surface B and its value, and the
source files the values came from.

Scope honesty: this checks DATA consistency between surfaces. It does not
load a live store, place an order, or run a checkout. See README.md.
"""

from __future__ import annotations

import csv
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

SURFACES = ("page", "feed", "structured")
PRODUCT_FIELDS = ("price", "currency", "availability", "identifier")
POLICY_FIELDS = ("shipping", "returns")

_AVAILABILITY_MAP = {
    "instock": "in_stock",
    "in_stock": "in_stock",
    "in stock": "in_stock",
    "available": "in_stock",
    "yes": "in_stock",
    "outofstock": "out_of_stock",
    "out_of_stock": "out_of_stock",
    "out of stock": "out_of_stock",
    "unavailable": "out_of_stock",
    "no": "out_of_stock",
}


def normalize_price(raw) -> str:
    """Canonical price: two-decimal string, currency symbols stripped."""
    text = str(raw).strip().replace("$", "").replace("€", "").replace(",", "")
    try:
        return str(Decimal(text).quantize(Decimal("0.01")))
    except InvalidOperation as exc:
        raise ValueError(f"unparseable price: {raw!r}") from exc


def normalize_currency(raw) -> str:
    return str(raw).strip().upper()


def normalize_availability(raw) -> str:
    text = str(raw).strip()
    # schema.org URLs: https://schema.org/InStock
    text = text.rstrip("/").rsplit("/", 1)[-1]
    key = text.strip().lower()
    if key in _AVAILABILITY_MAP:
        return _AVAILABILITY_MAP[key]
    raise ValueError(f"unrecognised availability value: {raw!r}")


def normalize_identifier(raw) -> str:
    return str(raw).strip().upper()


def normalize_policy(raw) -> str:
    return " ".join(str(raw).split()).strip().lower()


_NORMALIZERS = {
    "price": normalize_price,
    "currency": normalize_currency,
    "availability": normalize_availability,
    "identifier": normalize_identifier,
    "shipping": normalize_policy,
    "returns": normalize_policy,
}


# ---------------------------------------------------------------- extraction

def _first_offer(offers) -> dict:
    """JSON-LD allows offers as a single object or a list of objects."""
    if isinstance(offers, list):
        return offers[0] if offers else {}
    return offers or {}

def _extract_page(path: Path) -> tuple[dict, dict]:
    """Return (products, policies) from page.html."""
    html = path.read_text(encoding="utf-8")
    products: dict[str, dict] = {}
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    )
    if not match:
        raise ValueError(f"{path}: no JSON-LD block found")
    data = json.loads(match.group(1))
    items = data.get("@graph") or [data]
    for item in items:
        if item.get("@type") != "Product":
            continue
        offer = _first_offer(item.get("offers"))
        pid = item.get("productID") or item.get("sku")
        products[pid] = {
            "price": offer.get("price"),
            "currency": offer.get("priceCurrency"),
            "availability": offer.get("availability"),
            "identifier": item.get("sku"),
        }
    policies = {}
    for field in POLICY_FIELDS:
        m = re.search(
            rf'data-policy="{field}"[^>]*>(.*?)</', html, re.DOTALL | re.IGNORECASE
        )
        if m:
            policies[field] = m.group(1).strip()
    return products, policies


def _extract_feed(path: Path) -> tuple[dict, dict]:
    """Return (products, policies) from feed.csv (policies ride on each row)."""
    products: dict[str, dict] = {}
    policies: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pid = row["id"]
            products[pid] = {
                "price": row["price"],
                "currency": row["currency"],
                "availability": row["availability"],
                "identifier": row["sku"],
            }
            for field in POLICY_FIELDS:
                if row.get(field):
                    policies[field] = row[field]
    return products, policies


def _extract_structured(path: Path) -> tuple[dict, dict]:
    """Return (products, policies) from structured.json."""
    data = json.loads(path.read_text(encoding="utf-8"))
    products: dict[str, dict] = {}
    for item in data.get("products", []):
        offer = _first_offer(item.get("offers"))
        pid = item.get("productID") or item.get("sku")
        products[pid] = {
            "price": offer.get("price"),
            "currency": offer.get("priceCurrency"),
            "availability": offer.get("availability"),
            "identifier": item.get("sku"),
        }
    return products, dict(data.get("policies") or {})


_EXTRACTORS = {
    "page": ("page.html", _extract_page),
    "feed": ("feed.csv", _extract_feed),
    "structured": ("structured.json", _extract_structured),
}


# ------------------------------------------------------------------ checking

def check_store(store_dir: str | Path) -> dict:
    """Check one fixture store directory. Returns a report dict."""
    store_dir = Path(store_dir)
    per_surface: dict[str, tuple[dict, dict]] = {}
    for surface, (filename, extractor) in _EXTRACTORS.items():
        per_surface[surface] = extractor(store_dir / filename)

    product_ids = sorted(
        set().union(*(set(p) for p, _ in per_surface.values()))
    )
    conflicts: list[dict] = []

    def compare(scope: str, field: str, values: dict[str, tuple[object, str]]):
        """values: surface -> (normalised value, source filename)."""
        present = {s: v for s, v in values.items() if v[0] is not None}
        distinct = {v[0] for v in present.values()}
        if len(distinct) <= 1:
            return
        # Report each disagreeing pair against the first surface in order.
        ordered = [s for s in SURFACES if s in present]
        base = ordered[0]
        for other in ordered[1:]:
            if present[other][0] != present[base][0]:
                conflicts.append(
                    {
                        "scope": scope,
                        "field": field,
                        "surface_a": base,
                        "value_a": present[base][0],
                        "source_a": present[base][1],
                        "surface_b": other,
                        "value_b": present[other][0],
                        "source_b": present[other][1],
                    }
                )

    for pid in product_ids:
        for field in PRODUCT_FIELDS:
            values = {}
            for surface, (filename, _) in _EXTRACTORS.items():
                raw = per_surface[surface][0].get(pid, {}).get(field)
                values[surface] = (
                    _NORMALIZERS[field](raw) if raw is not None else None,
                    filename,
                )
            compare(pid, field, values)

    for field in POLICY_FIELDS:
        values = {}
        for surface, (filename, _) in _EXTRACTORS.items():
            raw = per_surface[surface][1].get(field)
            values[surface] = (
                _NORMALIZERS[field](raw) if raw is not None else None,
                filename,
            )
        compare("store", field, values)

    return {
        "store": store_dir.name,
        "products_checked": product_ids,
        "verdict": "CONSISTENT" if not conflicts else "CONFLICTS",
        "conflicts": conflicts,
    }


def format_report(report: dict) -> str:
    lines = [
        f"store: {report['store']}",
        f"products checked: {', '.join(report['products_checked'])}",
        f"verdict: {report['verdict']}",
    ]
    for c in report["conflicts"]:
        lines.append(
            "  CONFLICT {scope} · {field}: {sa}={va!r} ({srca}) vs "
            "{sb}={vb!r} ({srcb})".format(
                scope=c["scope"],
                field=c["field"],
                sa=c["surface_a"],
                va=c["value_a"],
                srca=c["source_a"],
                sb=c["surface_b"],
                vb=c["value_b"],
                srcb=c["source_b"],
            )
        )
    return "\n".join(lines)
