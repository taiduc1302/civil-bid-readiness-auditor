# User workflow

1. Start the local server and open the displayed `http://127.0.0.1` URL.
2. Upload a CSV or XLSX export, or load the synthetic sample.
3. Review detected worksheets and column mapping. Include only estimate sheets; leave cover/summary sheets excluded. If required fields are not automatically matched, select the CSV/XLSX columns for Description, Quantity, Unit, and Rate; blank mappings are allowed only for optional fields.
4. Run the audit.
5. Filter or read findings by Critical, High, Medium, and Low severity; inspect the sheet and row evidence.
6. Use the score only as a review-status indicator. Resolve findings with a qualified estimator and source documents.
7. Download the findings CSV or printable management-summary HTML.
8. Close the application; uploaded content was never persisted by the application.

Unsupported: encrypted/password-protected files, legacy `.xls`, images/PDFs, macros, formula evaluation, and files with no readable rows.
