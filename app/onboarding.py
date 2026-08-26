"""Static fictional onboarding content for the local review workflow."""
from __future__ import annotations


def guide_body() -> str:
    return """
<div class='notice'><strong>Fictional training data only.</strong> This walkthrough teaches the review workflow. It does not prove estimate correctness, reference authority, bid readiness, or HeavyBid import validity.</div>
<section class='card'>
<h2>1. Start with the synthetic estimate</h2>
<p>Use the bundled synthetic sample to see an intentionally imperfect estimate create a deterministic review queue.</p>
<form action='/sample' method='post'><button type='submit'>Run synthetic sample</button></form>
</section>
<section class='card'>
<h2>2. Confirm mapping, then audit</h2>
<p>Review Description, Quantity, Unit, and Rate before running the audit. Optional hierarchy/resource mappings stay editable even when preselected.</p>
<p>After audit, focus on affected rows, priority rows, rule evidence, and source row linkage. The legacy score is secondary and is not a certification.</p>
</section>
<section class='card'>
<h2>3. Work the review queue</h2>
<p>Try Priority/Open quick views, free-text search, and filters. Sort by priority, source, rule, sheet, or review status; optionally group by sheet, rule, or review status.</p>
<p>Use the page skip links to move between filters, findings, and references with the keyboard.</p>
</section>
<section class='card'>
<h2>4. Record human dispositions</h2>
<p>Try Reviewed, Needs correction, Accepted, or Suppressed on fictional findings. Suppressed requires a reason. Review state never edits the estimate or deterministic finding.</p>
</section>
<section class='card'>
<h2>5. Explore governed reference evidence</h2>
<p>For reference practice, use the bundled fictional HeavyBid-style resource export and fictional Activity/Resource reference CSV files. An optional revision/label is recorded exactly as entered.</p>
<p>Reference metadata records role, filename, revision/label, byte size, and SHA-256 with <code>authority_status=NOT_ESTABLISHED_BY_APP</code>. MATCH or a recorded hash does not establish authority.</p>
</section>
<section class='card'>
<h2>6. Export a review snapshot</h2>
<p>Download the review package ZIP after reviewing findings and optional references. It can contain manifest.json, findings.csv, review.csv, summary.html, README.txt, and references.csv.</p>
<p>Original estimate/reference bytes are intentionally excluded. The ZIP is a review snapshot, not a project database, bid approval, or HeavyBid artifact.</p>
</section>
<section class='card'>
<h2>Safety state</h2>
<p><code>NOT_PRODUCTION_READY=true</code><br><code>NOT_ESTIMATOR_VALIDATED=true</code><br><code>HEAVYBID_IMPORT_VALIDATED=false</code></p>
<p><a href='/'>Back to home</a></p>
</section>
"""
