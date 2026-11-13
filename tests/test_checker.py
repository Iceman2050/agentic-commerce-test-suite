"""Tests: every fixture store must produce exactly its expected verdict,
and the normalisers must behave on the variants real feeds use."""

import json
from pathlib import Path

import pytest

from commerce_suite.checker import (
    check_store,
    normalize_availability,
    normalize_currency,
    normalize_identifier,
    normalize_price,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "v1"
STORES = sorted(p.name for p in FIXTURES.iterdir() if (p / "expected.json").exists())


def _key(c):
    return (c["scope"], c["field"], c["surface_a"], c["value_a"],
            c["surface_b"], c["value_b"])


@pytest.mark.parametrize("store", STORES)
def test_store_matches_expected(store):
    expected = json.loads((FIXTURES / store / "expected.json").read_text())
    report = check_store(FIXTURES / store)
    assert report["verdict"] == expected["verdict"]
    assert sorted(map(_key, report["conflicts"])) == sorted(map(_key, expected["conflicts"]))


def test_consistent_store_has_zero_conflicts():
    report = check_store(FIXTURES / "consistent-store")
    assert report["verdict"] == "CONSISTENT"
    assert report["conflicts"] == []
    assert report["products_checked"] == ["bottle-002", "lamp-001"]


@pytest.mark.parametrize("store,field", [
    ("price-mismatch", "price"),
    ("currency-mismatch", "currency"),
    ("inventory-disagreement", "availability"),
    ("policy-conflict", "shipping"),
    ("identifier-mismatch", "identifier"),
])
def test_each_variant_plants_exactly_one_conflict(store, field):
    report = check_store(FIXTURES / store)
    assert len(report["conflicts"]) == 1
    assert report["conflicts"][0]["field"] == field
    # Conflicts carry their sources, so a reader can find both values.
    c = report["conflicts"][0]
    assert c["source_a"] in ("page.html", "feed.csv", "structured.json")
    assert c["source_b"] in ("page.html", "feed.csv", "structured.json")
    assert c["source_a"] != c["source_b"]


def test_clean_product_in_dirty_store_stays_clean():
    """The second product in every variant store is consistent; the checker
    must not smear one product's conflict onto it."""
    for store in STORES:
        if store == "consistent-store":
            continue
        report = check_store(FIXTURES / store)
        assert all(c["scope"] != "bottle-002" for c in report["conflicts"]), store


def test_normalize_price():
    assert normalize_price("$49.99") == "49.99"
    assert normalize_price("49.9") == "49.90"
    assert normalize_price(24.5) == "24.50"


def test_normalize_currency():
    assert normalize_currency("usd") == "USD"
    assert normalize_currency(" EUR ") == "EUR"


def test_normalize_availability_variants():
    assert normalize_availability("https://schema.org/InStock") == "in_stock"
    assert normalize_availability("OutOfStock") == "out_of_stock"
    assert normalize_availability("in_stock") == "in_stock"
    with pytest.raises(ValueError):
        normalize_availability("maybe")


def test_normalize_identifier():
    assert normalize_identifier(" lamp-001 ") == "LAMP-001"
