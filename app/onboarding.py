"""Static fictional onboarding content for the local review workflow."""
from __future__ import annotations

from accessibility import install_accessibility_semantics

install_accessibility_semantics()


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
<p>Use the attention summary, Priority/Open quick views, free-text search, and filters. Sort by priority, source, rule, sheet, or review status; optionally group by sheet, rule, or review status.</p>
<p>Use the page skip links to move between attention, filters, findings, and references with the keyboard.</p>
</section>
<section class='card'>
<h2>4. Record human dispositions</h2>
<p>Try Reviewed, Needs correction, Accepted, or Suppressed on fictional findings. Suppressed requires a reason. Review state never edits the estimate or deterministic finding.</p>
</section>
<section class='card'>
<h2>5. Explore governed reference evidence</h2>
<p>Start a separate fictional structured estimate. It uses the bundled HeavyBid-style resource-export fixture and opens the same editable mapping page used by normal uploads.</p>
<form action='/sample-structured' method='post'><button type='submit'>Run structured fictional sample</button></form>
<p>After auditing that sample, download one or both fictional references and upload them manually in the Governed reference validation section:</p>
<p><a class='button' href='/demo/reference/activity'>Download fictional Activity reference CSV</a> <a class='button' href='/demo/reference/resource'>Download fictional Resource reference CSV</a></p>
<p><strong>References are never auto-applied.</strong> An optional revision/label is recorded exactly as entered. Reference metadata records role, filename, revision/label, byte size, and SHA-256 with <code>authority_status=NOT_ESTABLISHED_BY_APP</code>. MATCH or a recorded hash does not establish authority.</p>
</section>
<section class='card'>
<h2>6. Review reference results</h2>
<p>The reference view starts with Exceptions and supports status/type filters, metadata-aware search, sorting, and grouping. These controls change only the presentation view.</p>
</section>
<section class='card'>
<h2>7. Export and verify a review snapshot</h2>
<p>Download the review package ZIP after reviewing findings and optional references. It contains review/report files plus <code>integrity.json</code>; original estimate/reference bytes are intentionally excluded.</p>
<p>Return to the home page and use <strong>Verify review package ZIP</strong> to check recorded member structure and hashes without restoring a review session.</p>
</section>
<section class='card'>
<h2>Safety state</h2>
<p><code>NOT_PRODUCTION_READY=true</code><br><code>NOT_ESTIMATOR_VALIDATED=true</code><br><code>HEAVYBID_IMPORT_VALIDATED=false</code></p>
<p><a href='/'>Back to home</a></p>
</section>
"""
