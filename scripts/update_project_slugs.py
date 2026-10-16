#!/usr/bin/env python3
"""Regenerate guides/project-slugs.mdx from the live 01Resolved API.

Reads API_KEY (required) and API_BASE_URL (default https://api.01resolved.com/v1)
from the environment. Writes the page only when its content changes, and prints
whether it did, so a scheduled job can commit just the real updates.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("API_BASE_URL", "https://api.01resolved.com/v1").rstrip("/")
KEY = os.environ.get("API_KEY")
PAGE = Path(__file__).resolve().parent.parent / "guides" / "project-slugs.mdx"


def get(path):
    """GET a path, waiting out the per-key rate limit when it is hit."""
    for _ in range(10):
        req = urllib.request.Request(BASE + path, headers={"x-api-key": KEY})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as err:
            if err.code != 429:
                raise
            try:
                wait = json.loads(err.read())["meta"].get("retry_after", 10)
            except Exception:
                wait = 10
            time.sleep(wait + 1)
    raise RuntimeError(f"still rate limited after retries: {path}")


def all_pages(path):
    items, page = [], 1
    while True:
        body = get(f"{path}?limit=50&page={page}")
        batch = body.get("data") or []
        items += batch
        if not batch or page >= (body.get("meta") or {}).get("totalPages", 1):
            return items
        page += 1
        time.sleep(2.2)


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("-" * (len(h) + 2) for h in header) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def render(coins, orgs, graveyard):
    coin_slugs = {c["organizationSlug"] for c in coins}
    dead_slugs = {g["organizationSlug"] for g in graveyard}
    others = [o for o in orgs if o["organizationSlug"] not in coin_slugs | dead_slugs]
    by_name = lambda name: name.lower()

    coin_rows = [
        [c.get("organizationName") or c["organizationSlug"], f'`{c["organizationSlug"]}`', c.get("tokenSymbol") or "—"]
        for c in sorted(coins, key=lambda c: by_name(c.get("organizationName") or c["organizationSlug"]))
    ]
    other_rows = [
        [o["organizationName"], f'`{o["organizationSlug"]}`']
        for o in sorted(others, key=lambda o: by_name(o["organizationName"]))
    ]
    dead_rows = [
        [g["title"], f'`{g["organizationSlug"]}`', g.get("tokenSymbol") or "—",
         (g.get("reasonStatus") or "").capitalize(), (g.get("dateEnded") or "")[:10]]
        for g in sorted(graveyard, key=lambda g: g.get("dateEnded") or "", reverse=True)
    ]

    return f"""---
title: "Project Slugs"
description: "Every tracked project and the slug to use for it in API calls."
icon: "list"
---

Use these values in the `slug` query parameter, or the `{{slug}}` path parameter.

<Note>
  This page updates automatically from the API, so new listings appear here without a docs release.
</Note>

---

## Ownership Coins

Projects that launched an ownership coin through MetaDAO, Futardio, or Backable. Full coverage: overview, financials, and decision markets.

{table(["Project", "Slug", "Token"], coin_rows)}

---

## Other Tracked DAOs

Projects that use decision markets but did not launch an ownership coin. Covered for decision markets only.

{table(["Project", "Slug"], other_rows)}

---

## Wound Down

Projects whose ownership coin has been liquidated or wound down. Historical data remains available. See `/v1/global-dashboard/graveyard-launches` for details.

{table(["Project", "Slug", "Token", "Outcome", "Ended"], dead_rows)}

---

## Example Usage

```bash
# MetaDAO treasury overview
curl -H "x-api-key: YOUR_KEY" \\
  "https://api.01resolved.com/v1/dao/treasury/overview?slug=metadao"

# Sanctum proposal list
curl -H "x-api-key: YOUR_KEY" \\
  "https://api.01resolved.com/v1/proposal?slug=sanctum&status=resolved"

# Drift trading activity
curl -H "x-api-key: YOUR_KEY" \\
  "https://api.01resolved.com/v1/trading-activity/drift"
```
"""


def main():
    if not KEY:
        sys.exit("API_KEY is not set")
    coins = all_pages("/global-dashboard/projects-launch")
    time.sleep(2.2)
    orgs = all_pages("/global-dashboard/projects")
    time.sleep(2.2)
    graveyard = all_pages("/global-dashboard/graveyard-launches")
    if not coins or not orgs:
        sys.exit("API returned an empty project list; refusing to overwrite the page")

    new = render(coins, orgs, graveyard)
    old = PAGE.read_text() if PAGE.exists() else ""
    if new == old:
        print("project-slugs.mdx unchanged")
        return
    PAGE.write_text(new)
    print(f"project-slugs.mdx updated: {len(coins)} coins, "
          f"{len(orgs) - len(coins) - len(graveyard)} other DAOs, {len(graveyard)} wound down")


if __name__ == "__main__":
    main()
