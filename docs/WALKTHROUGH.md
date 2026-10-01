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

## Current requested demo: real Email/Web Push, simulated WhatsApp

This is a partial assessment demo: WhatsApp remains simulated at the user's request. Do not claim actual WhatsApp receipt or mark the original three-channel requirement complete.

Production settings: `NOTIFICATIONS_DRY_RUN=false`, `WHATSAPP_DRY_RUN=true`. A local `.env` does not automatically configure Render. Secrets belong only in private local files and Render, never in the video or GitHub.

Postmark account approval can restrict recipients to the verified sender domain (error 412). A valid API token and verified sender do not bypass that restriction. Use an authorized test inbox on that domain while waiting, or wait for approval to test Gmail.

### Hinglish recording script, 5-7 minutes

1. Intro: "Maine Django REST API aur React se notification management system banaya hai. Backend Render aur frontend Vercel par hai. PostgreSQL mein templates aur delivery records store hote hain."
2. Sign in using the deployed admin account. Hide the password. Show the Login/Logout matrix. Say: "Trigger batata hai message kab bhejna hai; channel batata hai kahan bhejna hai."
3. Show My profile: saved authorized email, international-format phone, consent checkboxes, registered browser. Do not remove the working subscription.
4. Edit Login Email title to "Login demo" and body to "Hello {{name}}, your login demo is complete." Keep name mapped to user.name; save and show preview. Use Email Test send and show the actual inbox message. Show Web Push Test send and the actual browser notification. Show WhatsApp Test send as simulated, explicitly explaining that no Meta request is sent.
5. Fire the real Logout action. Show delivery evidence, then log in again and show Login delivery evidence. These authentication actions are the actual triggers; Test send only tests an individual template.
6. Toggle Login Email off, log out/in, and show the Login email delivery as skipped because the channel is disabled. The Logout email can still arrive because its toggle is separate. Restore Login Email to enabled.
7. Explain Delivery activity: simulated means no send, accepted means provider accepted (inbox/browser receipt is separate proof), skipped has a reason, failed needs configuration/provider investigation.
8. Show GitHub, README and live URLs. State WhatsApp simulation and any unverified receipt honestly. Upload the narrated recording, check link access, and share it with the repository and both deployment URLs.

System flow: React action -> authenticated Django endpoint -> persisted event -> enabled template and consent checks -> variable rendering -> one delivery per channel/recipient -> provider adapter or simulation -> persisted delivery status. Channel failure does not block successful authentication or other channels.
