# Fixture format (v1)

A fixture store is a directory with four files. Three are *surfaces* —
three independent descriptions of the same store. The fourth is the
ground truth the checker is graded against.

## `page.html` — the product page surface

An HTML page containing:

- One `<script type="application/ld+json">` block whose `@graph` holds
  one `Product` object per product:
  - `productID` — stable product key, matched across surfaces
  - `sku` — the identifier field
  - `name`
  - `offers.price`, `offers.priceCurrency`,
    `offers.availability` (schema.org URL, e.g.
    `https://schema.org/InStock`)
- A policies section with one element per policy, marked
  `data-policy="shipping"` and `data-policy="returns"`; the element
  text is the policy statement.

## `feed.csv` — the syndicated feed surface

CSV with header:

```
id,sku,title,price,currency,availability,shipping,returns
```

One row per product. `availability` uses feed spelling (`in_stock` /
`out_of_stock`). `shipping` and `returns` repeat the store's policy
statements on every row, as real feeds do.

## `structured.json` — the standalone structured-data surface

```json
{
  "products": [
    {"productID": "...", "sku": "...", "name": "...",
     "offers": {"price": "...", "priceCurrency": "...",
                "availability": "https://schema.org/InStock"}}
  ],
  "policies": {"shipping": "...", "returns": "..."}
}
```

## `expected.json` — ground truth (not a surface)

```json
{
  "store": "<directory name>",
  "verdict": "CONSISTENT" | "CONFLICTS",
  "conflicts": [
    {"scope": "<product id>" | "store", "field": "<field>",
     "surface_a": "page", "value_a": "<normalised>",
     "surface_b": "feed" | "structured", "value_b": "<normalised>"}
  ]
}
```

The checker never reads `expected.json`; `verify` and the tests compare
its computed findings against it.

## Normalisation rules

| Field | Rule |
|---|---|
| price | currency symbols stripped, compared as an exact 2-decimal value |
| currency | upper-cased |
| availability | schema.org URLs and feed spellings mapped to `in_stock` / `out_of_stock` |
| identifier | trimmed, upper-cased |
| shipping / returns | whitespace-collapsed, lower-cased exact text |
