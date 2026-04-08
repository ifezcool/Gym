Instructions for the MCP-enabled GPT:
You are an expert Dash/Python developer tasked with debugging and fixing a specific issue in the AVON HMO Portal codebase. Only edit the code in the exact files and sections needed — do not add new files, change unrelated features, or introduce new dependencies.
Relevant files (in this exact order of priority):

Exact problem to investigate and fix (do this investigation first):
In the contact center view (the view used by contact-centre staff to search enrollee/member records — it is rendered via the functions in combined.py that are called from the provider/wellness portal), searching for certain records returns zero results / empty table.
The user had already implemented (or believed they had implemented) the same logic that already works perfectly in the claims view:

Default to showing the most recent data (latest policy year).
Allow the user to select a previous policy year via a dropdown/selector.
The search/filter then correctly returns matching records from the selected (or default most-recent) policy year.

This logic is missing, broken, or not applied in the contact center view, which is why some records (especially those tied to older policy years or not matching an implicit “current-year-only” filter) turn up nothing.
Step-by-step actions you must execute perfectly (follow exactly, in order):

Open pages/combined.py.
Locate the two main view sections:
The claims view code (look for any function/callback/layout block containing “claims”, policy-year dropdown, most-recent default logic, data filtering, or table rendering for claims).
The contact center view code (look for the rendering function called by render_ps_layout / show_ps_portal or any block that builds the contact-centre / enrollee-search UI — it will use similar stores and data callbacks as the claims view).

Compare the data-loading, search/filter callback(s), policy-year handling, and table-display logic between the two views side-by-side.
Identify the precise root cause (it will be one or more of the following, which you must confirm):
The contact-center search/filter callback does not read or apply the policy-year selector.
No policy-year dropdown exists (or it is not wired to the callback) in the contact-center layout.
The SQL query or pandas filtering in the contact-center path hard-codes or defaults to only the current year instead of the most recent available year.
The “most recent data” default (sorting by policy year descending or using MAX(policy_year)) is missing or not applied on initial load / before search.
The data store / DataFrame for contact-center records is not being filtered the same way as claims.

Fix the issue by making the contact-center view’s logic identical to the working claims view for:
Policy-year selector (dropdown populated dynamically from the available years in the loaded data).
Default selection = most recent policy year.
Search/filter callback that respects the selected policy year (or defaults to most recent) and returns matching records.
Any shared helper functions for data loading or filtering must be reused (do not duplicate code).

Ensure the fix only affects the contact-center view — the claims view and all other portals must remain completely unchanged.
After editing, the contact-center search must now:
Return records for the searches that previously returned nothing.
Default to the most recent policy year on load.
Allow switching to any previous policy year and instantly update the results.

Verify the change locally (run the Dash app, navigate to the contact-center view, perform the same searches that were failing, and test the policy-year selector).