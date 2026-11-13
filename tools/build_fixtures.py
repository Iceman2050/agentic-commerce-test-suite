"""Generate the v1 fixture stores deterministically.

Every store, product and value here is invented. Each store directory gets
four files: page.html, feed.csv, structured.json, expected.json. Running
this script regenerates them byte-for-byte; the planted conflicts live in
the STORES table below and nowhere else.

    python tools/build_fixtures.py
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "v1"

BASE_POLICIES = {
    "shipping": "Free shipping on orders over $50",
    "returns": "Free returns within 30 days",
}


def product(pid, sku, name, price, currency="USD", availability="in_stock"):
    return {
        "id": pid,
        "sku": sku,
        "name": name,
        "price": price,
        "currency": currency,
        "availability": availability,
    }


# Each store: the same products described three times (page / feed /
# structured). A variant store differs from its own page surface on exactly
# one surface and one field — that is the planted conflict.
STORES = {
    "consistent-store": {
        "name": "Northwind Home Goods (fixture store)",
        "page": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "feed": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "structured": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "policies": {s: dict(BASE_POLICIES) for s in ("page", "feed", "structured")},
        "expected_conflicts": [],
    },
    "price-mismatch": {
        "name": "Harbor & Pine Outfitters (fixture store)",
        "page": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "feed": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "44.99"),  # planted
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "structured": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "policies": {s: dict(BASE_POLICIES) for s in ("page", "feed", "structured")},
        "expected_conflicts": [
            {"scope": "lamp-001", "field": "price", "surface_a": "page",
             "value_a": "49.99", "surface_b": "feed", "value_b": "44.99"},
        ],
    },
    "currency-mismatch": {
        "name": "Casa Verde Living (fixture store)",
        "page": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99", "USD"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50", "USD"),
        ],
        "feed": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99", "USD"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50", "USD"),
        ],
        "structured": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99", "EUR"),  # planted
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50", "USD"),
        ],
        "policies": {s: dict(BASE_POLICIES) for s in ("page", "feed", "structured")},
        "expected_conflicts": [
            {"scope": "lamp-001", "field": "currency", "surface_a": "page",
             "value_a": "USD", "surface_b": "structured", "value_b": "EUR"},
        ],
    },
    "inventory-disagreement": {
        "name": "Summit Supply Co (fixture store)",
        "page": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99", availability="in_stock"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "feed": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99", availability="out_of_stock"),  # planted
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "structured": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99", availability="in_stock"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "policies": {s: dict(BASE_POLICIES) for s in ("page", "feed", "structured")},
        "expected_conflicts": [
            {"scope": "lamp-001", "field": "availability", "surface_a": "page",
             "value_a": "in_stock", "surface_b": "feed", "value_b": "out_of_stock"},
        ],
    },
    "policy-conflict": {
        "name": "Blue Mesa Mercantile (fixture store)",
        "page": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "feed": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "structured": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "policies": {
            "page": dict(BASE_POLICIES),
            # planted: feed advertises a different shipping policy
            "feed": {**BASE_POLICIES, "shipping": "Flat $6.95 shipping on all orders"},
            "structured": dict(BASE_POLICIES),
        },
        "expected_conflicts": [
            {"scope": "store", "field": "shipping", "surface_a": "page",
             "value_a": "free shipping on orders over $50",
             "surface_b": "feed", "value_b": "flat $6.95 shipping on all orders"},
        ],
    },
    "identifier-mismatch": {
        "name": "Foxglove & Co (fixture store)",
        "page": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "feed": [
            product("lamp-001", "LAMP-001", "Aurora Desk Lamp", "49.99"),
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "structured": [
            product("lamp-001", "LAMP-100", "Aurora Desk Lamp", "49.99"),  # planted SKU
            product("bottle-002", "BTL-002", "Trailhead Insulated Bottle", "24.50"),
        ],
        "policies": {s: dict(BASE_POLICIES) for s in ("page", "feed", "structured")},
        "expected_conflicts": [
            {"scope": "lamp-001", "field": "identifier", "surface_a": "page",
             "value_a": "LAMP-001", "surface_b": "structured", "value_b": "LAMP-100"},
        ],
    },
}

_SCHEMA_AVAIL = {"in_stock": "https://schema.org/InStock",
                 "out_of_stock": "https://schema.org/OutOfStock"}


def render_page(store_name: str, products: list, policies: dict) -> str:
    graph = []
    cards = []
    for p in products:
        graph.append({
            "@type": "Product",
            "productID": p["id"],
            "sku": p["sku"],
            "name": p["name"],
            "offers": {
                "@type": "Offer",
                "price": p["price"],
                "priceCurrency": p["currency"],
                "availability": _SCHEMA_AVAIL[p["availability"]],
            },
        })
        cards.append(
            f'    <article class="product" id="{p["id"]}">\n'
            f'      <h2>{p["name"]}</h2>\n'
            f'      <p class="price">{p["currency"]} {p["price"]}</p>\n'
            f'      <p class="sku">SKU: {p["sku"]}</p>\n'
            f"    </article>"
        )
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, indent=2)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{store_name}</title>\n"
        f'<script type="application/ld+json">\n{ld}\n</script>\n'
        "</head>\n<body>\n"
        f"  <h1>{store_name}</h1>\n"
        "  <!-- Synthetic fixture page. Invented store, invented products. -->\n"
        + "\n".join(cards)
        + '\n  <section class="store-policies">\n'
        f'    <p data-policy="shipping">{policies["shipping"]}</p>\n'
        f'    <p data-policy="returns">{policies["returns"]}</p>\n'
        "  </section>\n</body>\n</html>\n"
    )


def render_feed(products: list, policies: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["id", "sku", "title", "price", "currency",
                     "availability", "shipping", "returns"])
    for p in products:
        writer.writerow([p["id"], p["sku"], p["name"], p["price"], p["currency"],
                         p["availability"], policies["shipping"], policies["returns"]])
    return buf.getvalue()


def render_structured(products: list, policies: dict) -> str:
    doc = {
        "note": "Standalone structured-data surface for this fixture store.",
        "products": [
            {
                "@type": "Product",
                "productID": p["id"],
                "sku": p["sku"],
                "name": p["name"],
                "offers": {
                    "price": p["price"],
                    "priceCurrency": p["currency"],
                    "availability": _SCHEMA_AVAIL[p["availability"]],
                },
            }
            for p in products
        ],
        "policies": policies,
    }
    return json.dumps(doc, indent=2) + "\n"


def main() -> None:
    for slug, store in STORES.items():
        out = ROOT / slug
        out.mkdir(parents=True, exist_ok=True)
        (out / "page.html").write_text(
            render_page(store["name"], store["page"], store["policies"]["page"]),
            encoding="utf-8")
        (out / "feed.csv").write_text(
            render_feed(store["feed"], store["policies"]["feed"]), encoding="utf-8")
        (out / "structured.json").write_text(
            render_structured(store["structured"], store["policies"]["structured"]),
            encoding="utf-8")
        expected = {
            "store": slug,
            "verdict": "CONSISTENT" if not store["expected_conflicts"] else "CONFLICTS",
            "conflicts": store["expected_conflicts"],
        }
        (out / "expected.json").write_text(
            json.dumps(expected, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {slug}")


if __name__ == "__main__":
    main()
