# Data model

## Canonical input fields

| Field | Required | Accepted aliases |
|---|---:|---|
| `description` | yes | description, item, item description, bid item, scope |
| `quantity` | yes | quantity, qty, quantity total |
| `unit` | yes | unit, uom, unit of measure |
| `rate` | yes | rate, unit rate, price, unit price |
| `amount` | no | amount, total, extended amount, cost |
| `category` | no | category, cost category, type |
| `markup_pct` / `margin_pct` | no | markup, markup %, margin, margin % |
| `bid_item` | no | bid item no, bid item number, biditem, biditem code, bid item code |
| `activity` | no | activity, activity code, activity id |
| `resource_type` | no | resource type, resource class, cost type |
| `resource_code` | no | resource code, resource id, resource no, resource number |

Rows retain original text values and a private `__source_row` parser field; published findings use `sheet` and `row` evidence fields. Supported numeric values are finite base-10 decimals and may include currency symbols, commas, and percent signs. `NaN`, `Infinity`, and `-Infinity` are invalid; formula text is not executed or evaluated.

## Optional estimating hierarchy

The auditor remains compatible with flat generic estimate exports. When available, the optional hierarchy fields provide additional context roughly equivalent to:

`Bid Item -> Activity -> Resource`

The hierarchy is not required and is not treated as a vendor-specific HeavyBid schema. It is used only to reduce false-positive comparisons. In particular, duplicate/conflict rules compare repeated descriptions inside the same available hierarchy context rather than treating every identical description in the workbook as the same scope.

## Conservative UOM normalization

The auditor normalizes only spelling or notation variants that do not require a quantity conversion. Examples include `HR / HRS / HOUR -> hr`, `EA / EACH -> ea`, `LS / LUMP SUM -> ls`, and common metre/square-metre/cubic-metre notation variants.

Measurement bases that can carry different physical or commercial meaning remain distinct. In particular:

- `BCY`, `LCY`, and `CCY` are not treated as interchangeable.
- US `TON` and metric `t / tonne` remain distinct.
- No length, area, volume, mass, density, swell, shrink, or currency conversion is performed.

The original source UOM remains unchanged in the uploaded data. Normalization is used only for deterministic comparison keys such as duplicate/unit consistency and rate peer groups.

Rate-outlier review groups use normalized `unit` plus the strongest available class (`resource_type`, otherwise `category`). At least four positive rates must exist in a peer group before the outlier rule runs. This prevents unlike units such as LS, HR, EA, TON, and LF from being compared against one global file median.

## Output finding

`id, severity, rule_id, sheet, row, field, message, evidence, recommended_action`

## Review metrics

The result includes `review_metrics` so large estimates are not represented primarily by a score that can quickly bottom out at zero:

- `status`: highest operational review level implied by deterministic findings
- `finding_count`: total findings
- `affected_rows`: unique source rows with one or more findings
- `affected_row_percent`: affected rows divided by rows reviewed
- `priority_rows`: unique rows with Critical or High findings
- `summary_findings`: findings not tied to one source row

The legacy 0-100 score remains for backward compatibility but is secondary to severity and affected-row metrics. Neither the score nor review metrics validate bid correctness or readiness.
