Do not modify any callback signatures, IDs, store components, or database logic. Only change the specific areas described below.

Fix 1 — Contact Center: Booking Details Table with Visible Borders
File: pages/combined.py
Location: Inside the search_enrollee callback, in the section that returns booking details for a searched member ID. Find the block that builds table_rows using a list comprehension over booking.iterrows(), then renders an html.Table.
Problem: The booking details table has no visible borders or styling, making it look loosely arranged and inconsistent with the rest of the portal.
Solution: Replace the existing html.Table element with a styled version. The table should use the same visual language as the rest of the portal — specifically:

The html.Table element should have style with width: 100%, borderCollapse: collapse, border: 1px solid #E9D8FD (a light purple border matching the design system), borderRadius: 10px, overflow: hidden, and fontSize: 0.875rem.
Each html.Tr row should have a bottom border of 1px solid #F3F4F6 and alternate row background using the same #F5F3FF pattern used in the data tables elsewhere.
The label html.Td (left column, the field name) should be styled with fontWeight: 600, color: #374151, padding: 10px 14px, width: 40%, backgroundColor: #F9FAFB, borderRight: 1px solid #E9D8FD.
The value html.Td (right column) should have color: #111827, padding: 10px 14px.
Apply alternating row background by checking row index: even rows get #FFFFFF, odd rows get #F5F3FF as background on the label cell.

The easiest way to implement alternating rows is to enumerate booking.iterrows() and use the index parity to set the label cell background.

Fix 2 — Home Page: Hide Gym Portal, Center Wellness Portal
File: pages/home.py
Location: The cards_section variable, specifically the dbc.Row containing two dbc.Col elements — one for Gym Portal and one for Wellness Portal.
Problem: Both portal cards are shown side by side. The Gym Portal card should be hidden but remain in the code so it can be re-enabled easily.
Solution:

Add a boolean constant near the top of home.py, right after the imports, called SHOW_GYM_PORTAL = False. This is the single toggle — changing it to True later re-enables the gym card with no other changes needed.
In the dbc.Row, wrap the Gym Portal dbc.Col so that it is only included in the row's children if SHOW_GYM_PORTAL is True. The cleanest approach: build the row children as a Python list, conditionally append the gym col, always append the wellness col, then pass the list to the dbc.Row.
When SHOW_GYM_PORTAL is False, the wellness dbc.Col should use width={"size": 6, "offset": 3} instead of xs=12, md=6 so that it is centred on the page at a reasonable width rather than stretching full-width. When SHOW_GYM_PORTAL is True, restore both columns to xs=12, md=6 as they currently are.


Fix 3 — Provider View: Active Button State Indicator
File: pages/combined.py
Location: The update_provider_content callback, which handles clicks on provider-nav-view-btn and provider-nav-submit-btn, and also the ps_provider_layout variable where those two buttons are defined.
Problem: There is no visual feedback indicating which of the two sidebar buttons — "View Wellness Enrollees" or "Submit Wellness Results" — is currently active.
Solution — Two parts:
Part A — Add an Output for active button state.
The update_provider_content callback currently only outputs to provider-content. Add a second Output targeting a new dcc.Store component with id provider-active-view, storing either "view" or "submit" depending on which button was clicked. Add this dcc.Store to the ps_provider_layout layout alongside the existing content.
Part B — Add a callback to style the buttons.
Add a new callback that takes provider-active-view store as Input and outputs updated style dicts to both provider-nav-view-btn and provider-nav-submit-btn.
Define two style states:

Active style: background: linear-gradient(135deg, #3B0F8C, #5B21B6) (a noticeably darker version of the brand purple), color: white, border: none, borderRadius: 8px, textAlign: left, padding: 10px 14px, fontWeight: 700, boxShadow: inset 0 2px 6px rgba(0,0,0,0.2), borderLeft: 3px solid #EDE9FE.
Inactive style: background: linear-gradient(135deg, #5B21B6, #7C3AED), color: white, border: none, borderRadius: 8px, textAlign: left, padding: 10px 14px, fontWeight: 500.

When provider-active-view is "view", apply active style to provider-nav-view-btn and inactive to provider-nav-submit-btn. When it is "submit", reverse this. Default (no store value) should show "view" as active.

Fix 4 — Landing Page: Reduce Vertical Space / Scrolling
File: pages/home.py
Location: The hero section and cards_section variables.
Problem: On an average laptop screen the hero section is very tall, requiring scrolling to see the portal cards.
Solution — reduce padding throughout:

In the hero section, change padding from "72px 24px 56px" to "40px 24px 32px".
In cards_section, change padding from "48px 24px 80px" to "24px 24px 40px".
In the hero, change the logo-container marginBottom from "24px" to "14px".
Change the html.H1 margin from "0 auto 12px" to "0 auto 8px".
Remove the two decorative blob html.Div elements (the radial gradient circles positioned absolutely at top-left and bottom-right) — they add no functional value on a compact layout and their sizes (320px, 280px) contribute to the perceived height of the section.


Fix 5 — Wellness Questionnaire: Remove Pre-selected Answers
File: pages/combined.py
Location: The build_health_questionnaire function.
Problem: All radio button groups have pre-selected default values: Family History questions default to 'Nobody', Personal Medical History to 'No', Surgical History to 'No', and Health Survey to 'Never'. This means users may submit without consciously answering every question.
Solution: For every dbc.RadioItems component inside build_health_questionnaire, change value=... to value=None. This removes all pre-selections. Do not change anything else — not the options, not the IDs, not the labels.
There are four groups of questions:

Family questions — currently value='Nobody' → change to value=None
Personal medical questions — currently value='No' → change to value=None
Surgical history questions — currently value='No' → change to value=None
Health survey questions — currently value='Never' → change to value=None

Apply this change to every single dbc.RadioItems inside this function. No other changes.

Fix 6 — Client Services: Email Notification on Provider Change
File: pages/combined.py
Location: The update_member_provider callback, triggered by plans-change-submit-btn.
Problem: When a member's wellness provider is updated via the "Update Member's Wellness Provider" modal in the ClientServices view, no notification email is sent. The contact centre needs to know so they can revoke the old PA code and issue a new one.
Solution: After the database UPDATE executes successfully and invalidate_cache() is called, before returning the success alert, add an email send step using the existing smtplib pattern already used throughout the file. The email should:

Sender: noreply@avonhealthcare.com using the email_password environment variable (same pattern as send_pa_code_email).
Recipient: ifeoluwa.adeniyi@avonhealthcare.com (hardcoded for now as specified).
Subject: WELLNESS PROVIDER CHANGE — PA CODE ACTION REQUIRED
Body (HTML): The body should clearly communicate:

That the wellness provider for the member has been changed.
The Member ID (the member_id variable already in scope).
The old provider (the old_provider value retrieved from the database before the update — this is already fetched and stored as old_provider in the existing code).
The new provider (the new_provider variable).
The current PA code for the member. This is not currently fetched in this callback. Add a database read: before the UPDATE, execute a SELECT to retrieve the IssuedPACode for this member from demo_tbl_annual_wellness_enrollee_data WHERE MemberNo = ? — store it as current_pa_code. If it is null or empty, display "None issued" in the email.
A clear instruction that the existing PA code has been revoked and a new PA code must be issued to the member for the new provider.
Use the same HTML table style used in other emails in this file for the details section, with the purple header style (#59058D background, white text).


Use smtplib.SMTP('smtp.office365.com', 587) with starttls() and login() as seen in the other email functions.
If the email fails, do not block the success response — still return the success alert, but append a warning note to it such as " (Note: notification email failed to send.)" so the user knows.
If the email succeeds, return the success alert unchanged: "Provider updated successfully!".