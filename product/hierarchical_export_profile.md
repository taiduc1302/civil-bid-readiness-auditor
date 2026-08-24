# Generic hierarchical civil estimate export profile

This profile describes a vendor-neutral structure that can represent common civil estimating exports while remaining compatible with the auditor's existing canonical fields.

## Required canonical fields

- `description`
- `quantity`
- `unit`
- `rate`

## Recommended optional hierarchy fields

- `bid_item`
- `activity`
- `resource_type`
- `resource_code`

## Recommended source columns

A structured export can contain columns similar to:

- Bid Item No
- Bid Item Description
- Activity Code
- Activity Description
- Resource Type
- Resource Code
- Description
- Quantity
- Unit
- Rate
- Amount
- Category
- Notes

The auditor only maps the fields it needs. Descriptive hierarchy columns can remain present for human context even when they are not canonical fields.

## Controlled adapter principle

The core audit engine must remain vendor-neutral. Vendor-specific export support should be implemented as a thin mapping/profile layer that converts known source headers into the canonical model.

For a HeavyBid-style export, the intended semantic mapping is approximately:

`Bid Item -> Activity -> Resource`

but the core model must not depend on HeavyBid-specific database tables, proprietary identifiers, internal company codebooks, or invented activity/resource codes.

## Safety boundaries

- Never infer missing quantities or rates.
- Never convert BCY/LCY/CCY automatically.
- Never convert US tons to metric tonnes automatically.
- Never invent resource types or codes when the export does not supply them.
- Never treat a deterministic finding as proof that an estimate line is wrong.
- Keep company-specific codebook validation in a separate governed profile/reference layer.

## Synthetic fixture

`samples/synthetic_hierarchical_civil_estimate.csv` is fictional and contains intentionally planted review conditions. It is designed to exercise:

- Bid Item / Activity / Resource context
- normalized hourly UOM variants
- rate peer grouping
- BCY versus LCY separation
- exact duplicate detection
- extension mismatch detection
- zero placeholder detection

The file contains no employer, supplier, client, or live project data.
