# agentic-commerce-test-suite

A test suite an AI shopping agent — or a store owner — can run against a
store's product data to check **cross-surface consistency**: the same
product, described on a product page, in a product feed, and in
structured data, must tell the same story about price, currency,
availability, identity, shipping and returns. Six synthetic fixture
stores, one fully consistent and five with exactly one planted conflict
each, plus a checker that reads all three surfaces and reports either
`CONSISTENT` or the exact conflict — field, both values, and the files
they came from.

## The problem

An AI shopping agent does not read your store the way a person does. It
reads surfaces: the product page's structured data, the feed your
platform syndicates, the JSON-LD a search engine cached. Each surface is
usually produced by a different system — the theme, a feed plugin, a
catalogue export — and they drift apart silently. The page says $49.99,
the feed says $44.99. The page says USD, the structured data says EUR.
The page says in stock, the feed says out of stock. A human visitor
sees one of those and never knows. An agent sees all of them, cannot
tell which is true, and either quotes the wrong price, refuses to
recommend the product, or transacts on the wrong terms.

The stores that will work with shopping agents are the ones whose
surfaces agree. That agreement is testable — before an agent ever
visits. This repo is that test, in fixture form: ground truth where the
correct answer for every store is known in advance, so a checker (this
one, or yours) can be proven against it instead of trusted.

## Honesty labelling — read this first

- **What is TESTED here:** data consistency. The checker reads three
  static surfaces of each fixture store and compares six fields. That
  comparison really runs, on the files in this repo, and its output is
  recorded below.
- **What is SIMULATED:** the stores themselves. Every store, product
  and value is invented; the fixtures imitate the *shape* of a page, a
  feed and a structured-data document, at miniature scale.
- **What is NOT tested:** a real checkout. This suite never loads a
  live store, never adds anything to a cart, never touches payment,
  authorization or order state. A separate sandbox-transaction test
  would be needed for that, and this repo does not pretend to be one.
- **A consistent fixture proves the checker catches planted conflicts.**
  It does not prove any real store is correct, complete, or safe to
  buy from. Consistency is necessary for an agent to trust a store's
  data; it is nowhere near sufficient.
- Verdicts are per field and per product: one product's conflict never
  smears onto a clean product in the same store, and the tests assert
  exactly that.

## The six fixture stores (v1)

Each store sells the same two invented products (Aurora Desk Lamp,
Trailhead Insulated Bottle) on three surfaces: `page.html` (product
page with JSON-LD and a policies section), `feed.csv` (the syndicated
feed), and `structured.json` (the standalone structured-data document).
Variant stores plant their conflict on the first product only; the
second product stays consistent everywhere, so a correct checker must
find exactly one conflict and leave the clean product alone.

| Store | Planted conflict | Expected verdict |
|---|---|---|
| `consistent-store` | none | CONSISTENT, 0 conflicts |
| `price-mismatch` | page $49.99 vs feed $44.99 | 1 conflict: price |
| `currency-mismatch` | page/feed USD vs structured EUR | 1 conflict: currency |
| `inventory-disagreement` | page in stock vs feed out of stock | 1 conflict: availability |
| `policy-conflict` | page "Free shipping on orders over $50" vs feed "Flat $6.95 shipping on all orders" | 1 conflict: shipping |
| `identifier-mismatch` | page/feed SKU LAMP-001 vs structured LAMP-100 | 1 conflict: identifier |

Fixtures are generated deterministically by `tools/build_fixtures.py`;
the planted conflicts live in that script's `STORES` table and nowhere
else. Regenerate with `python tools/build_fixtures.py`. The per-store
`expected.json` is the ground truth the tests check against — the
checker computes its findings from the surfaces themselves, never from
`expected.json`.

## Quick start

Requires Python 3.10+. No dependencies for the checker; `pytest` for
the tests.

```bash
# Check every fixture store against its expected results
python -m commerce_suite verify fixtures/v1

# Human-readable report for all stores
python -m commerce_suite check-all fixtures/v1

# One store, machine-readable
python -m commerce_suite check fixtures/v1/price-mismatch --json

# Test suite
python -m pytest
```

## Expected vs actual (recorded 2026-11-13, v1.0.0)

`python -m commerce_suite verify fixtures/v1` — exit 0:

```
consistent-store: OK (expected CONSISTENT, got CONSISTENT, 0 conflict(s))
currency-mismatch: OK (expected CONFLICTS, got CONFLICTS, 1 conflict(s))
identifier-mismatch: OK (expected CONFLICTS, got CONFLICTS, 1 conflict(s))
inventory-disagreement: OK (expected CONFLICTS, got CONFLICTS, 1 conflict(s))
policy-conflict: OK (expected CONFLICTS, got CONFLICTS, 1 conflict(s))
price-mismatch: OK (expected CONFLICTS, got CONFLICTS, 1 conflict(s))
```

Full findings, exactly as the checker prints them:

```
store: consistent-store
products checked: bottle-002, lamp-001
verdict: CONSISTENT

store: currency-mismatch
products checked: bottle-002, lamp-001
verdict: CONFLICTS
  CONFLICT lamp-001 · currency: page='USD' (page.html) vs structured='EUR' (structured.json)

store: identifier-mismatch
products checked: bottle-002, lamp-001
verdict: CONFLICTS
  CONFLICT lamp-001 · identifier: page='LAMP-001' (page.html) vs structured='LAMP-100' (structured.json)

store: inventory-disagreement
products checked: bottle-002, lamp-001
verdict: CONFLICTS
  CONFLICT lamp-001 · availability: page='in_stock' (page.html) vs feed='out_of_stock' (feed.csv)

store: policy-conflict
products checked: bottle-002, lamp-001
verdict: CONFLICTS
  CONFLICT store · shipping: page='free shipping on orders over $50' (page.html) vs feed='flat $6.95 shipping on all orders' (feed.csv)

store: price-mismatch
products checked: bottle-002, lamp-001
verdict: CONFLICTS
  CONFLICT lamp-001 · price: page='49.99' (page.html) vs feed='44.99' (feed.csv)
```

Tests: **17 passed** (`python -m pytest -q`), covering every store
against its expected verdict, the exactly-one-conflict property per
variant, clean-product isolation, and the normalisers (price,
currency, schema.org and feed availability spellings, SKU).

## Using it against your own store

Point the same three-surface shape at real data: save a product page's
HTML as `page.html`, your feed export as `feed.csv` (columns: `id, sku,
title, price, currency, availability, shipping, returns`), and your
structured-data document as `structured.json`, in one directory, then
run `python -m commerce_suite check <dir>`. Field formats are specified
in `docs/FORMAT.md`. What you get back is a consistency report on those
snapshots — a statement about the files you fed it, at the moment you
saved them, not a live audit and not a checkout test.

## Scope and limitations

- **Fields:** price, currency, availability, identifier (SKU),
  shipping policy, returns policy. Variants, GTIN/MPN cross-checks,
  tax, discounts and multi-currency price tables are out of scope
  for v1.
- **Comparison is normalised, not fuzzy:** prices compare as exact
  decimals after symbol stripping, policies as normalised text.
  "Free shipping over $50" vs "Free shipping on orders over $50"
  would be reported as a conflict. That strictness is deliberate —
  an agent cannot know two different sentences mean the same policy —
  but it means wording drift in policies reads as a conflict.
- **Two disagreeing surfaces are reported against the page;** if the
  feed and structured data disagree with each other but both happen to
  differ from the page, the report names the page pairs. The page is
  treated as the reference surface because it is the one a merchant
  edits most directly — a convention, not a truth claim.
- **Fixtures are miniature:** two products per store, one conflict per
  variant. Real catalogues are larger and messier; these fixtures are
  a test floor for checkers, not a survey of everything feeds get
  wrong.
- **No checkout, no live fetching, no store platform integrations.**
  See the honesty section above.

## Relationship to AgentReady and Store Audit

[AgentReady](https://agentready.getingeniousai.com) is the cross-surface
product truth engine: it fetches a real store's page, feed, structured
data and policies and shows the precise conflicts and fixes. This suite
is its open, standalone ground truth — the fixture laboratory where the
conflict classes it looks for are planted, known and checkable.
[Store Audit](https://storeaudit.getingeniousai.com) covers the other
half of agent-readiness: whether the purchase path itself behaves
(cart, checkout handoff, order state), which this suite deliberately
does not test. Data consistency first, transaction conformance second —
labelled separately, because they are different claims.

## License

MIT. Built by Ingenious AI — https://getingeniousai.com

## Ingenious AI platforms

Built by Ingenious AI. The fleet — every platform does one job:

- [Agent Auth Gateway](https://authgateway.getingeniousai.com) · [MandateGuard](https://mandateguard.getingeniousai.com) · [Agentic Receipts](https://agentic-receipts.getingeniousai.com) · [Agent Flight Recorder](https://flightrecorder.getingeniousai.com) · [TrustGate](https://trustgate.getingeniousai.com) · [BoundaryVault](https://boundaryvault.getingeniousai.com) · [Rogue-Agent Defense](https://rogue-defense.getingeniousai.com) · [AgentGate](https://agentgate.getingeniousai.com) · [Agent Passport](https://agentpassport.getingeniousai.com) · [HomeShield](https://homeshield.getingeniousai.com) · [AgentBlock](https://agentblock.getingeniousai.com) · [ChatBreaker](https://chatbreaker.getingeniousai.com) · [EvalScope](https://evalscope.getingeniousai.com) · [CompanionGuard](https://companionguard.getingeniousai.com)
- [DomainGuard](https://domainguard.getingeniousai.com) · [BreachHunter](https://breachhunter.getingeniousai.com) · [TakedownCoop](https://takedowncoop.getingeniousai.com) · [WireWatch](https://wirewatch.getingeniousai.com) · [CallbackShield](https://callbackshield.getingeniousai.com) · [Vibe-Code Audit](https://vibe-audit.getingeniousai.com)
- [DisclosureGuard](https://disclosureguard.getingeniousai.com) · [ProvenanceGuard](https://provenanceguard.getingeniousai.com) · [ADMT](https://admt.getingeniousai.com) · [ReviewDesk](https://reviewdesk.getingeniousai.com) · [CRAClock](https://craclock.getingeniousai.com) · [AI Audit Exchange](https://auditexchange.getingeniousai.com) · [TermsWatch](https://termswatch.getingeniousai.com) · [ModelMinder](https://modelminder.getingeniousai.com) · [ReviewProof](https://reviewproof.getingeniousai.com) · [EInvoice](https://einvoice.getingeniousai.com) · [DueLadder](https://dueladder.getingeniousai.com) · [OutcomeMeter](https://outcomemeter.getingeniousai.com)
- [AgentReady](https://agentready.getingeniousai.com) · [Store Audit](https://storeaudit.getingeniousai.com) · [ContentCraft AI](https://contentcraft.getingeniousai.com) · [GEOFixer](https://geofixer.getingeniousai.com)
- Full directory: https://getingeniousai.com/platforms
