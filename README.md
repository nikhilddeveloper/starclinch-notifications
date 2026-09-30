# StarClinch notification system

Django REST API and React admin console for managing WhatsApp, email and browser-push notifications from one table. Login and Logout are connected to real authentication actions. The repository includes provider adapters, database migrations, tests, a Render blueprint, Vercel configuration and a narrated-demo checklist.

**Default mode is dry run.** It exercises the application without contacting a provider. A simulated or provider-accepted result is not proof of receipt. Real sandbox sends require your own credentials, template approval, consent and allowlisted recipients. Hosting and live delivery must be verified before submitting the assessment.

## Quick start on Windows

Requirements: Python 3.10+ (3.12 recommended), Node.js 20+ (22 LTS recommended), npm and Git.

From this project directory in PowerShell:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock.txt
Copy-Item backend\.env.example backend\.env
cd backend
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py seed_demo
..\.venv\Scripts\python.exe manage.py createsuperuser
..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
~~~

In a second terminal, from this project directory:

~~~powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
~~~

Open http://localhost:5173 and sign in using the superuser you created. There is no hardcoded admin password. The API is at http://localhost:8000/api and health check at http://localhost:8000/api/health/.

On Linux/macOS use python3, .venv/bin/python and cp in place of the Windows commands.

1. Open **My profile**; save your own email, WhatsApp number in E.164 form, and consent choices.
2. Open **Notification settings**. The seed command creates Login and Logout with six enabled templates. It never overwrites later edits.
3. Edit a template, map its named variables, and save. Test send targets the signed-in admin's profile and respects both toggles and consent.
4. Open **Delivery activity** to inspect results. With no provider configuration, email and WhatsApp can be simulated after profile setup; browser push is skipped until a subscription exists. Automated tests use synthetic subscriptions without claiming real delivery.
5. Log out, then sign in again. Each authentication action persists an event and dispatches the configured channels.

## What is implemented

- Staff-only trigger/template APIs and a responsive admin matrix: one row per trigger, one column per channel.
- Create/edit templates, trigger and channel toggles, per-cell test send, WhatsApp creation and approval polling through Sync.
- Named template variables mapped to user.name, user.email, event.name or event.time. Arbitrary object traversal and executable template code are not supported.
- Postmark transactional text emails with subjects and bodies authored in the admin panel. Content is stored locally; no Postmark template dashboard is needed.
- WhatsApp named variables converted into ordered numbered parameters. Content edits create a new local revision and require a new provider-approved version.
- OneSignal Web SDK subscription and targeted REST sends with Android/iOS explicitly disabled.
- Persistent event and delivery records, immutable message snapshots, independent channel failures, masked recipient logs, and a database-backed outbox.
- Expiring authentication tokens, logout revocation, staff permissions, input validation, recipient consent, sandbox allowlists and request throttling.
- Custom trigger creation and staff-only demo firing with an idempotency key. Login/Logout can only be fired by their actual authentication endpoints. Inactivity scheduling is outside the selected two-trigger scope.

## Real sandbox configuration

Edit backend/.env locally or the Render environment when deployed. Never put private keys in frontend variables, Git, screenshots or the video. Only the OneSignal app ID is public.

| Variable | Purpose |
| --- | --- |
| SECRET_KEY | Random Django signing key; mandatory with DEBUG=false |
| DEBUG | true locally, false on Render |
| DATABASE_URL | PostgreSQL URL for deployment; local default is SQLite |
| ALLOWED_HOSTS | Comma-separated hostnames; Render hostname is added automatically |
| FRONTEND_URL | Exact frontend origins, e.g. https://your-project.vercel.app; no trailing slash |
| NOTIFICATIONS_DRY_RUN | true for simulation; false for real sandbox API calls |
| NOTIFICATIONS_INLINE | true for immediate dispatch without an additional worker |
| WHATSAPP_ACCESS_TOKEN | Meta sandbox access token |
| PHONE_NUMBER_ID | Meta test phone-number ID |
| WHATSAPP_BUSINESS_ACCOUNT_ID | WABA ID; needed to create and query templates |
| WHATSAPP_API_VERSION | Configurable Graph API version, default v23.0 |
| POSTMARKAPP_TOKEN | Postmark server token |
| POSTMARK_FROM_EMAIL | Verified Postmark sender |
| ONESIGNAL_APP_ID | Website app UUID, also returned to the frontend |
| ONESIGNAL_REST_API_KEY | Private OneSignal App API key, server only |
| SANDBOX_EMAILS | Comma-separated allowed recipient emails |
| SANDBOX_PHONES | Comma-separated allowed E.164 phone numbers, including + |
| SANDBOX_PUSH_IDS | Comma-separated allowed OneSignal subscription UUIDs |
| ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD | Optional one-time hosted admin bootstrap |

### WhatsApp

Create a Meta app with the WhatsApp product. Use its test sender, temporary token, WABA ID and phone-number ID. Add your own phone to Meta's test recipient list and SANDBOX_PHONES. Token permissions must support messaging and business template management.

Turn off dry run only after all sandbox configuration is ready. In the admin panel, open a WhatsApp cell, author a policy-compliant template and save. Click **Sync** to submit it; later click Sync to poll status. Test send is only allowed by the backend after APPROVED. Meta controls approval and account permissions; the app does not manufacture approval. If your test WABA restricts custom templates, resolve that account restriction or ask the assessor how they want it handled. A preapproved hello_world message is not a substitute for two custom trigger templates.

Every content edit resets approval. This implementation submits a new version instead of silently changing an approved template. Old versions remain at Meta for traceability and may need later provider cleanup.

### Email

Set up a Postmark account/server and verify your sender. Configure POSTMARKAPP_TOKEN, POSTMARK_FROM_EMAIL and SANDBOX_EMAILS. Compose subject and body in the application's Email cell. Tests send plain-text transactional emails using the Postmark email API.

Some provider sandbox/test tokens accept API calls without delivering email. Use the provider's permitted testing configuration that can actually reach your verified address for the walkthrough. Plan allowances in the assessment may be outdated; check the provider before relying on any free quota.

### Browser push

Create a **website** app in OneSignal and set the exact frontend origin. For localhost, enable the provider's supported localhost setup. Deploy the included OneSignalSDKWorker.js at the root of the frontend. Set the backend app ID and private key.

Sign in, open My profile and click **Subscribe this browser**. Allow browser notifications. Copy the subscription UUID shown there into SANDBOX_PUSH_IDS on the backend and restart/redeploy the backend. Send a test from the Web Push cell. If permission was denied, reset site notification permission in your browser.

The first login happens before a new browser has subscribed, so that first push is correctly skipped. Subscribe once, then log out and log in again to test both triggers. Subscriptions intentionally persist through logout for the assignment's Logout notification; remove them explicitly when finished, especially on shared devices. The server prevents reassigning an existing subscription to another account.

## Architecture and delivery semantics

~~~text
React console / authentication actions
               |
        Django REST API
               |
    transaction: event + delivery snapshots
               |
     inline dispatcher / optional worker
         |          |          |
    WhatsApp     Postmark    OneSignal
               |
   delivery status and provider message ID
~~~

Trigger has many templates, with a database uniqueness constraint on (trigger, channel). Each event belongs to a user and has a unique deduplication key. A delivery belongs to the event and captures the recipient and rendered template revision. Browser subscriptions support multiple devices.

Events and deliveries commit before provider requests. A conditional database update claims each queued delivery once. Idempotency prevents re-enqueueing the same custom event. Provider errors affect only that delivery; authentication still completes if a channel fails.

Default inline delivery is intentionally simple for a small assessment deployment: it requires no Redis or paid worker. Three provider calls can delay a login/logout response by up to their combined timeouts; multiple browser subscriptions add more calls. Gunicorn is configured accordingly. For background operation, set NOTIFICATIONS_INLINE=false and run **python manage.py process_notifications** continuously against the same PostgreSQL database. The --once flag drains one batch.

Statuses: queued, sending, accepted, simulated, failed, skipped. Accepted confirms an API message ID, not delivery/read status. This scope has no provider delivery webhooks. There are no automatic retries after timeouts: the provider may already have accepted a message, and retrying could duplicate it. A process crash after claiming can leave a delivery in sending; inspect provider state before any manual recovery. This is not an exactly-once distributed delivery guarantee.

Rate limits use Django's local-memory cache and are per process. A larger deployment should use a shared cache, stronger per-recipient limits and a dedicated task queue. Session tokens are stored in sessionStorage and expire after 12 hours; login rotates the account's single active token. A production multi-device account flow would use per-device sessions. The backend enforces sandbox allowlists even if profile data is edited.

## Tests

~~~powershell
cd backend
..\.venv\Scripts\python.exe manage.py test notifications
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
cd ..\frontend
npm test
npm run build
~~~

Backend tests cover authentication, staff permissions, consent/toggles, duplicate events, snapshot integrity, channel failure isolation, approval lifecycle, payload contracts and secret-safe error handling. Frontend tests cover the matrix, editing, toggles, error displays, simulation labels and API session handling. Tests use mocked provider calls and never send real messages. CI also runs backend tests against PostgreSQL; local test results alone do not verify hosted PostgreSQL or external provider delivery.

## Deployment and handoff

See [Deployment guide](docs/DEPLOYMENT.md), [API guide](docs/API.md), and [Walkthrough checklist](docs/WALKTHROUGH.md). The email requests submission within 24 hours, while the document says two days; use the email deadline unless HR confirms otherwise.

Submit the GitHub repository, Render backend URL, Vercel frontend URL, admin access instructions shared securely, and a voice-narrated recording showing actual receipt on all three channels for both triggers. No live URLs or video are claimed by this repository.

## Provider references

- [Meta WhatsApp API collection](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api)
- [Postmark Email API](https://postmarkapp.com/developer/api/email-api)
- [OneSignal push API](https://documentation.onesignal.com/reference/push-notification)
- [OneSignal Web SDK](https://documentation.onesignal.com/docs/en/web-sdk-reference)
- [Django on Render](https://render.com/docs/deploy-django)
- [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite)

Queued dry-run messages retain their simulation flag even if the server switches to real delivery before the queue drains. Template edits are revalidated under a database row lock to prevent inconsistent mappings from overlapping edits.
