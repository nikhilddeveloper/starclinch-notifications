# Walkthrough recording checklist

Record this only after real sandbox delivery has been verified. This guide is a script outline, not a completed video. Use your own words and explain the implementation you understand. Hide API tokens, passwords, phone numbers and unrelated messages.

## Suggested sequence

1. Introduce the problem: one admin table controls templates for three channels and two real website triggers. Explain Django/React, Render/Vercel and PostgreSQL.
2. Sign in as admin. Show Login and Logout rows and the three columns.
3. Open My profile and explain consent, sandbox recipients and browser subscription. Do not expose full personal details unnecessarily.
4. Create or edit a template. Show named variables, mappings and the preview. For WhatsApp, explain approval and show Sync returning APPROVED after review. Approval can take longer than the recording; finish it beforehand and state that accurately.
5. Test Login templates and show real receipt on your phone, email and browser. A provider message ID alone is not receipt proof.
6. Log out to fire Logout; show all three notifications with its different message text. Log back in and show all three Login notifications.
7. Turn one channel off, repeat the relevant action, and show its skipped delivery. Turn it back on.
8. Edit an email or push message and test the changed text. This avoids waiting for WhatsApp reapproval during the recording.
9. Briefly show models, permission checks, event/delivery service, provider adapters and tests. Explain dry run versus accepted versus actual receipt.
10. End with repository and live URLs. Upload the actual narrated screen recording to a reviewer-accessible location and test the sharing link.

## Explain without reading notes

**What is a trigger?** A website event or condition that starts a notification. Examples: a successful login, an order being placed, and a user being inactive for a week. This implementation connects Login and Logout; it does not pretend to schedule inactivity events.

**What are the three channels?** WhatsApp, transactional email and browser Web Push.

**Why author templates in the admin panel?** The admin can manage all event messages in one place. The backend stores content and settings and communicates with each provider. WhatsApp still controls its required approval.

**What is Web Push?** A notification delivered through a subscribed web browser, using its service worker and user permission. This assignment excludes native Android/iOS app push.

**How are failures handled?** Each channel has its own delivery record. A failed provider does not prevent other channels or successful authentication. Timeouts are treated as uncertain and are not blindly retried.

## Submission email draft

Hi Neha,

Please find my completed Backend Developer assessment below:

- GitHub repository: [insert verified repository URL]
- Backend on Render: [insert verified backend URL]
- Frontend on Vercel: [insert verified frontend URL]
- Narrated walkthrough: [insert accessible recording URL]
- Admin access: [share securely; do not put a password in a public README]

The implementation supports Login and Logout notifications through WhatsApp, email and Web Push, with template management, variable mappings, toggles and delivery logs. Setup instructions and tests are included in the README.

Thank you for reviewing my submission.

Best regards,
Nikhil

Replace every placeholder and verify every claim before sending. This repository does not send the email.
