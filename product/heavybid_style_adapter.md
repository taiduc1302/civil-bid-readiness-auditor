# Controlled HeavyBid-style adapter

This adapter is a thin compatibility layer for flat hierarchical resource exports that resemble common HeavyBid estimating reports. It is intentionally not a HeavyBid database integration.

## Supported semantic shape

The supported resource-export shape must clearly expose enough hierarchy to map:

`Bid Item -> Activity -> Resource`

plus the canonical audit fields:

- description
- quantity
- unit
- rate

Optional amount/category/resource-code fields are retained when present.

## Detection policy

Automatic detection is fail-closed. The adapter requires recognized source headers for:

- Bid Item
- Activity
- Resource Type
- Description
- Quantity
- Unit
- Rate

Matching is case-insensitive and whitespace-normalized only. No fuzzy matching is used. If the signature is incomplete, the adapter does not claim the export is supported; manual generic mapping remains available.

## Non-goals and safety boundaries

The adapter does not:

- access HeavyBid databases or APIs
- modify HeavyBid
- certify that a workbook can be imported into HeavyBid
- invent Bid Item, Activity, Resource, Crew, Production, Rate, or Quantity values
- validate Tybo/company codebooks
- convert BCY/LCY/CCY
- convert US tons and metric tonnes
- infer crew composition or production rates
- repair estimate values automatically

Company-specific codebook validation belongs in a separately governed reference layer. A project-specific baseline and explicit estimator approvals remain required before any future HeavyBid-readable output can be treated as controlled import material.

## Fixture

`samples/synthetic_heavybid_style_resource_export.csv` is fictional and contains no live employer, client, supplier, or tender data. It exists only to validate adapter behavior and deterministic audit integration.

## Import validation status

This adapter does not prove a production import path. Any future HeavyBid-readable output must continue to carry:

`HEAVYBID_IMPORT_VALIDATED=false`

until a real, independently reviewed HeavyBid test import succeeds.
