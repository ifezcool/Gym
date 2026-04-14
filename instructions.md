Change 1: Send Email to Contact Center on Wellness Form Submission
Location: In pages/combined.py, inside the submit_form callback function.
What to do: After the database INSERT succeeds (after the conn.connection.commit() line, before the success_msg is built), add a call to send an email notification to the contact center.
Email details:

Sender: noreply@avonhealthcare.com (use the existing email_password env variable, same SMTP setup as other emails in the file)
Recipient: ifeoluwa.adeniyi@avonhealthcare.com
Subject: WELLNESS BOOKING NOTIFICATION — ACTION REQUIRED: [MemberNo] (substitute actual member number)
Body (HTML): A simple message saying: "Dear Contact Centre, the following enrollee has completed their wellness booking and is awaiting a PA Code. Please log into the Contact Centre portal and issue a PA Code for this member." Then include a small HTML table with these fields: Member ID, Member Name, Client, Selected Provider, Appointment Date, Wellness Benefits, Date Submitted (today's date).
Do not block or fail the form submission if the email fails — just print the error silently. The success_msg should still show regardless.


Change 2: Fix the Contact Centre Search Returning Nothing
Location: In pages/combined.py, inside the search_enrollee callback function.
The bug: The callback has this condition near the top:
if not n_clicks or not enrollee_id:
    return cards_html
This means when n_clicks is None (first load) or enrollee_id is empty, it returns the overview table — that part is fine. But when the user clicks Search with a valid ID, the function queries query_ps_q2 using cached_read_sql, which pulls from the shared cache. The issue is that the cache was populated at login time, before the new record was inserted by the form submission. So the search finds no matching record because the cache is stale.
What to do: Inside search_enrollee, when n_clicks is provided and enrollee_id is not empty (i.e., the user clicked Search), do not use cached_read_sql for query_ps_q2. Instead, call invalidate_cache() first, then re-fetch fresh data directly using pd.read_sql(query_ps_q2, conn) with a live engine connection. This ensures the contact centre always sees the most recently submitted records when doing a lookup.
Alternatively, a simpler fix: at the top of the search_enrollee function body (regardless of whether a search was triggered), always call invalidate_cache() before the cached_read_sql(query_ps_q2) call. This is less efficient but guarantees freshness for the contact centre view, which is a low-traffic internal page where a small performance cost is acceptable.

Summary of Files to Touch
Only pages/combined.py needs changes — two locations:

Inside submit_form callback: add post-insert email to contact centre
Inside search_enrollee callback: force fresh DB read instead of cached data