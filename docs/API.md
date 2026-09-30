# API guide

Base URL: /api/. JSON requests and responses. Protected calls use **Authorization: Token <token>**. Login returns a token; logout revokes it. Staff means Django is_staff=true.

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | /health/ | Public | Database health |
| POST | /auth/login/ | Public, throttled | Username/password login; fires Login |
| POST | /auth/logout/ | Authenticated | Fires Logout, revokes token |
| GET, PATCH | /auth/me/ | Authenticated | Own name, email, phone and consent |
| GET | /config/ | Authenticated | Mode, public app ID, provider configuration booleans |
| POST, DELETE | /push-subscriptions/ | Authenticated | Own subscription UUID registration/removal |
| GET, POST | /triggers/ | Staff | List/create triggers |
| GET, PUT, PATCH | /triggers/{id}/ | Staff | Read/update a trigger; key is immutable |
| POST | /triggers/{id}/fire/ | Staff | Fire custom demo event; requires Idempotency-Key UUID |
| GET, POST | /templates/ | Staff | Paginated list/create template |
| GET, PUT, PATCH | /templates/{id}/ | Staff | Read/update template |
| POST | /templates/{id}/sync/ | Staff | Submit or poll WhatsApp approval |
| POST | /templates/{id}/test/ | Staff | Test using own profile; respects toggles/consent |
| GET | /deliveries/ | Authenticated | Staff: all logs; member: own logs |
| GET | /deliveries/{uuid}/ | Authenticated | Visible delivery detail |

Lists of deliveries support ?page=1&status=failed&channel=email. Page size is 30. Triggers are returned unpaginated for the admin matrix. Templates and delivery logs use standard count/next/previous/results pagination. There are no destructive trigger/template deletion endpoints; turn them off to preserve history.

Create a trigger:

~~~json
{"key":"order_placed","name":"Order placed","description":"Order completed on the website","enabled":true}
~~~

Create a template (use the returned trigger ID):

~~~json
{
  "trigger": 1,
  "channel": "email",
  "title": "Your {{event}} update",
  "body": "Hello {{name}}, your action completed at {{time}}.",
  "variable_mappings": {"name":"user.name","event":"event.name","time":"event.time"},
  "enabled": true
}
~~~

Channel values are whatsapp, email, push. Email and push require title. WhatsApp language defaults to en_US and category defaults to UTILITY. Template provider state and revision are read-only. A second template for the same trigger/channel is rejected. Unknown/missing mappings, malformed variables and unsupported sources are rejected.

For a real custom business event inside Django, call notifications.services.fire_event(key, user, deduplication_key) from the business transaction. Use a stable unique business key such as order:123:placed; reusing it returns the original event without sending again. Do not call the staff demo endpoint from untrusted clients for real business events.

HTTP statuses include 400 for invalid input, 401 for missing/expired authentication, 403 for insufficient permissions, 409 for a subscription owned by someone else, 429 for throttling and 502 for provider template-sync failures. A notification send failure is recorded on the delivery; it does not turn a successful login into an authentication failure. Test-send responses contain per-channel results and should be inspected even when HTTP status is 201.
