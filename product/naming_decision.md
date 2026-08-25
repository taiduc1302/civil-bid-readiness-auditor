# Product naming decision

## Decision

Adopt **Civil Estimate Review Auditor** as the public product title.

Keep the existing GitHub repository slug `civil-bid-readiness-auditor` for now so existing links and repository history remain stable.

## Why this name

### Civil Estimate Review Auditor

Selected because it:

- describes the implemented behavior directly;
- does not imply certification, approval, or commercial correctness;
- is understandable to estimators without extra explanation;
- leaves room for deterministic audit rules, governed reference checks, human review states, and controlled HeavyBid-oriented workflows;
- can remain valid even if the product later supports multiple estimating systems.

### Civil Estimate QA Auditor

Not selected because “QA” can still be interpreted as establishing or guaranteeing estimate quality, while the tool explicitly cannot establish correct scope, quantity, rates, productivity, commercial compliance, or bid readiness.

### Civil Estimate Review Queue

Not selected because the product now does more than maintain a queue: it includes deterministic checks, hierarchy-aware mapping, governed-reference evidence, review dispositions, and controlled output gates.

### Civil Bid Readiness Auditor

Retired as the preferred public title because “bid readiness” can be read as a certification claim that exceeds the implemented evidence contract.

## Positioning statement

> A local-first deterministic review tool for civil estimate exports that surfaces data-quality and governed-reference exceptions for qualified human review.

## Migration policy

1. README and product documentation use the new title immediately.
2. Repository slug stays unchanged unless a later migration decision justifies link disruption.
3. Runtime UI, report titles, test strings, and any future package metadata migrate in a dedicated compatibility PR.
4. Safety disclaimers remain unchanged or become more explicit; renaming must never weaken the non-certification boundary.
