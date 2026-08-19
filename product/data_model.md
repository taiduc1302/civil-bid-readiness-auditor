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

Rows retain original text values and a private `__source_row` parser field; published findings use `sheet` and `row` evidence fields. Supported numeric values are finite base-10 decimals and may include currency symbols, commas, and percent signs. `NaN`, `Infinity`, and `-Infinity` are invalid; formula text is not executed or evaluated.

## Output finding

`id, severity, rule_id, sheet, row, field, message, evidence, recommended_action`

The management summary includes score, severity counts, inputs reviewed, calculation method, and limitations.
