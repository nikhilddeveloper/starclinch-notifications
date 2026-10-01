import React, { useEffect, useRef, useState } from "react";
import { api, describeDeliveries } from "./api";
import { initPush, subscribe } from "./push";

const channels = [
  { key: "whatsapp", name: "WhatsApp", icon: "W", note: "Meta Cloud API" },
  { key: "email", name: "Email", icon: "@", note: "Postmark" },
  { key: "push", name: "Web Push", icon: "↗", note: "Browser only" },
];
const sourceOptions = ["user.name", "user.email", "event.name", "event.time"];
const samples = {
  "user.name": "Nikhil",
  "user.email": "nikhil@example.com",
  "event.name": "Login",
  "event.time": "2026-09-30 12:00 UTC",
};
export function preview(text, mappings) {
  return text.replace(
    /{{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*}}/g,
    (_, key) => samples[mappings[key]] || "[unmapped: " + key + "]",
  );
}
function Badge({ children, tone = "" }) {
  return <span className={"badge " + tone}>{children}</span>;
}
function Dialog({ title, children, close }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    el.showModal();
    return () => el.close();
  }, []);
  return (
    <dialog
      ref={ref}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      <div className="dialog-head">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={close}
          aria-label="Close dialog"
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  );
}
function TemplateEditor({ trigger, channel, template, close, saved }) {
  const [form, setForm] = useState({
    title: template?.title || "",
    body: template?.body || "Hello {{name}}, your notification is ready.",
    enabled: template?.enabled ?? false,
    language: template?.language || "en_US",
    category: template?.category || "UTILITY",
  });
  const [mappings, setMappings] = useState(
    template?.variable_mappings || { name: "user.name" },
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const keys = [
    ...new Set(
      (
        (form.title + " " + form.body).match(
          /{{\s*[a-zA-Z][a-zA-Z0-9_]*\s*}}/g,
        ) || []
      ).map((v) => v.slice(2, -2).trim()),
    ),
  ];
  const change = (e) =>
    setForm({
      ...form,
      [e.target.name]:
        e.target.type === "checkbox" ? e.target.checked : e.target.value,
    });
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const mapping = Object.fromEntries(
        keys.map((k) => [k, mappings[k] || "user.name"]),
      );
      await api("/templates/" + (template ? template.id + "/" : ""), {
        method: template ? "PATCH" : "POST",
        body: {
          ...form,
          trigger: trigger.id,
          channel,
          variable_mappings: mapping,
        },
      });
      await saved();
      close();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={
        (template ? "Edit" : "Create") +
        " " +
        channels.find((c) => c.key === channel).name +
        " template"
      }
      close={() => !busy && close()}
    >
      <p className="muted">
        {trigger.name} · Templates are managed here. WhatsApp content changes
        require a new approval.
      </p>
      <form onSubmit={save}>
        {channel !== "whatsapp" && (
          <label>
            {channel === "email" ? "Subject" : "Title"}
            <input
              name="title"
              value={form.title}
              onChange={change}
              maxLength={160}
              required
            />
          </label>
        )}
        <label>
          Message
          <textarea
            name="body"
            value={form.body}
            onChange={change}
            rows={4}
            maxLength={
              channel === "whatsapp" ? 1024 : channel === "push" ? 250 : 4000
            }
            required
          />
        </label>
        <p className="hint">
          Use named variables such as {"{{name}}"} or {"{{event}}"}. Map each
          one below.
        </p>
        {keys.map((k) => (
          <label className="mapping" key={k}>
            <code>{"{{" + k + "}}"}</code>
            <select
              aria-label={"Source for " + k}
              value={mappings[k] || "user.name"}
              onChange={(e) =>
                setMappings({ ...mappings, [k]: e.target.value })
              }
            >
              {sourceOptions.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        ))}
        {channel === "whatsapp" && (
          <div className="form-row">
            <label>
              Language
              <input
                name="language"
                value={form.language}
                onChange={change}
                required
              />
            </label>
            <label>
              Category
              <select name="category" value={form.category} onChange={change}>
                <option>UTILITY</option>
                <option>MARKETING</option>
              </select>
            </label>
          </div>
        )}
        <label className="check">
          <input
            type="checkbox"
            name="enabled"
            checked={form.enabled}
            onChange={change}
          />
          Enable this channel
        </label>
        <section className="preview">
          <span className="eyebrow">Sample preview</span>
          <strong>{preview(form.title, mappings)}</strong>
          <p>
            {preview(
              form.body,
              Object.fromEntries(
                keys.map((k) => [k, mappings[k] || "user.name"]),
              ),
            )}
          </p>
        </section>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-footer">
          <button
            type="button"
            className="secondary"
            onClick={close}
            disabled={busy}
          >
            Cancel
          </button>
          <button disabled={busy}>{busy ? "Saving…" : "Save template"}</button>
        </div>
      </form>
    </Dialog>
  );
}
function NewTrigger({ close, saved }) {
  const [form, setForm] = useState({ name: "", key: "", description: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/triggers/", { method: "POST", body: form });
      await saved();
      close();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Add a trigger" close={() => !busy && close()}>
      <p className="muted">
        A trigger describes a website event. New custom triggers can be fired
        from this demo; real application events must call the backend service.
      </p>
      <form onSubmit={save}>
        {["name", "key", "description"].map((k) => (
          <label key={k}>
            {k}
            <input
              value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              required={k !== "description"}
              pattern={k === "key" ? "[a-z][a-z0-9_]*" : undefined}
              maxLength={k === "key" ? 60 : k === "name" ? 100 : 300}
            />
          </label>
        ))}
        <p className="hint">
          Example key: order_placed. Keys cannot be renamed.
        </p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="dialog-footer">
          <button disabled={busy}>
            {busy ? "Creating…" : "Create trigger"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
function Profile({ user, config, saved, notify, busy, action }) {
  const [form, setForm] = useState(user);
  useEffect(() => setForm(user), [user]);
  async function save(e) {
    e.preventDefault();
    await action(async () => {
      const data = await api("/auth/me/", {
        method: "PATCH",
        body: {
          first_name: form.first_name,
          email: form.email,
          phone: form.phone,
          email_consent: form.email_consent,
          whatsapp_consent: form.whatsapp_consent,
        },
      });
      saved(data);
      notify("Notification profile saved.");
    });
  }
  async function registerPush() {
    await action(async () => {
      const id = await subscribe(config?.onesignal_app_id);
      await api("/push-subscriptions/", {
        method: "POST",
        body: { subscription_id: id },
      });
      saved(await api("/auth/me/"));
      notify(
        "Browser subscribed. For real sandbox sends, add this subscription ID to SANDBOX_PUSH_IDS on the backend.",
      );
    });
  }
  async function removePush(id) {
    await action(async () => {
      await api("/push-subscriptions/", {
        method: "DELETE",
        body: { subscription_id: id },
      });
      saved(await api("/auth/me/"));
      notify("Subscription removed from this account.");
    });
  }
  return (
    <div className="profile-grid">
      <section className="panel">
        <span className="eyebrow">Your test recipients</span>
        <h2>Notification profile</h2>
        <p className="muted">
          Use your own verified sandbox recipients. Login and Logout send to
          this profile.
        </p>
        <form onSubmit={save}>
          <div className="form-row">
            <label>
              First name
              <input
                value={form.first_name}
                onChange={(e) =>
                  setForm({ ...form, first_name: e.target.value })
                }
                maxLength={150}
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </label>
          </div>
          <label>
            WhatsApp phone
            <input
              type="tel"
              placeholder="+919876543210"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={form.email_consent}
              onChange={(e) =>
                setForm({ ...form, email_consent: e.target.checked })
              }
            />
            I agree to receive test emails.
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={form.whatsapp_consent}
              onChange={(e) =>
                setForm({ ...form, whatsapp_consent: e.target.checked })
              }
            />
            I agree to receive test WhatsApp messages.
          </label>
          <button disabled={busy}>Save profile</button>
        </form>
      </section>
      <section className="panel">
        <span className="eyebrow">Browser only</span>
        <h2>Web Push</h2>
        <p className="muted">
          Subscribe on this website, then log out and log back in to test both
          triggers. A first login cannot reach a browser that has not subscribed
          yet.
        </p>
        <button
          onClick={registerPush}
          disabled={busy || !config?.onesignal_app_id}
        >
          Subscribe this browser
        </button>
        {!config?.onesignal_app_id && (
          <p className="hint">OneSignal is not configured yet.</p>
        )}
        <ul className="subscriptions">
          {user.push_subscriptions.map((id) => (
            <li key={id}>
              <code>{id}</code>
              <button
                className="text-button"
                disabled={busy}
                onClick={() => removePush(id)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <p className="hint">
          Subscriptions remain registered after logout so the Logout
          notification can arrive. Use Remove on a shared device.
        </p>
      </section>
    </div>
  );
}
export default function App() {
  const [user, setUser] = useState(null),
    [config, setConfig] = useState(null),
    [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("templates"),
    [triggers, setTriggers] = useState([]),
    [logs, setLogs] = useState({ results: [], next: null, previous: null });
  const [editor, setEditor] = useState(null),
    [newTrigger, setNewTrigger] = useState(false),
    [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(""),
    [error, setError] = useState(""),
    [search, setSearch] = useState("");
  const [credentials, setCredentials] = useState({
    username: "",
    password: "",
  });
  const [logFilter, setLogFilter] = useState(""),
    [page, setPage] = useState(1);
  const notify = (message) => {
    setError("");
    setNotice(message);
  };
  async function action(fn) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  const refreshTriggers = () => api("/triggers/").then(setTriggers);
  const refreshLogs = () =>
    api("/deliveries/?page=" + page + "&status=" + logFilter).then(setLogs);
  async function loadSession() {
    const [me, cfg] = await Promise.all([api("/auth/me/"), api("/config/")]);
    setUser(me);
    setConfig(cfg);
    setTab(me.is_staff ? "templates" : "profile");
  }
  useEffect(() => {
    if (sessionStorage.getItem("notification_token"))
      loadSession()
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    else setLoading(false);
    const expired = () => {
      setUser(null);
      setConfig(null);
      setEditor(null);
      setNewTrigger(false);
    };
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    if (user?.is_staff) refreshTriggers().catch((e) => setError(e.message));
  }, [user?.id]);
  useEffect(() => {
    if (user && tab === "activity")
      refreshLogs().catch((e) => setError(e.message));
  }, [user?.id, tab, page, logFilter]);
  useEffect(() => {
    if (config?.onesignal_app_id)
      initPush(config.onesignal_app_id).catch(() => {});
  }, [config?.onesignal_app_id]);
  async function login(e) {
    e.preventDefault();
    await action(async () => {
      const result = await api("/auth/login/", {
        method: "POST",
        body: credentials,
      });
      sessionStorage.setItem("notification_token", result.token);
      setCredentials({ username: "", password: "" });
      await loadSession();
      notify("Login event recorded.\n" + describeDeliveries(result));
    });
  }
  async function logout() {
    await action(async () => {
      const result = await api("/auth/logout/", { method: "POST" });
      sessionStorage.removeItem("notification_token");
      setUser(null);
      setConfig(null);
      setTriggers([]);
      setLogs({ results: [] });
      notify("Signed out.\n" + describeDeliveries(result));
    });
  }
  async function toggle(template) {
    await action(async () => {
      await api("/templates/" + template.id + "/", {
        method: "PATCH",
        body: { enabled: !template.enabled },
      });
      await refreshTriggers();
    });
  }
  async function test(template) {
    await action(async () => {
      const result = await api("/templates/" + template.id + "/test/", {
        method: "POST",
      });
      notify(describeDeliveries(result));
    });
  }
  async function sync(template) {
    await action(async () => {
      const result = await api("/templates/" + template.id + "/sync/", {
        method: "POST",
      });
      await refreshTriggers();
      notify(
        "WhatsApp: " +
          result.provider_status +
          (result.provider_error ? " — " + result.provider_error : ""),
      );
    });
  }
  const enabled = triggers
    .flatMap((t) => t.templates)
    .filter((t) => t.enabled).length;
  const message = (
    <>
      {error && (
        <div className="message error" role="alert">
          <strong>Action needed</strong>
          <p>{error}</p>
        </div>
      )}
      {notice && (
        <div className="message" role="status">
          <p>{notice}</p>
          <button className="text-button" onClick={() => setNotice("")}>
            Dismiss
          </button>
        </div>
      )}
    </>
  );
  if (loading)
    return <main className="loading">Loading Notification Studio…</main>;
  if (!user)
    return (
      <main className="login-layout">
        <section className="login-story">
          <div className="brand">
            <span className="brand-icon">n</span>Notification Studio
          </div>
          <div>
            <span className="eyebrow">One event. Every channel.</span>
            <h1>
              Keep every
              <br />
              message in sync.
            </h1>
            <p>
              Manage the right message for each moment across WhatsApp, email,
              and browser push.
            </p>
            <div className="channel-pills">
              {channels.map((c) => (
                <span key={c.key}>
                  {c.icon} &nbsp;{c.name}
                </span>
              ))}
            </div>
          </div>
          <small>Backend developer assessment · StarClinch</small>
        </section>
        <section className="login-form">
          <span className="eyebrow">Welcome back</span>
          <h2>Sign in to your workspace</h2>
          <p className="muted">
            Signing in fires the Login trigger for your saved notification
            profile.
          </p>
          {message}
          <form onSubmit={login}>
            <label>
              Username
              <input
                autoComplete="username"
                value={credentials.username}
                onChange={(e) =>
                  setCredentials({ ...credentials, username: e.target.value })
                }
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={credentials.password}
                onChange={(e) =>
                  setCredentials({ ...credentials, password: e.target.value })
                }
                required
              />
            </label>
            <button className="full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in →"}
            </button>
          </form>
          <p className="hint">
            Use the admin account created during project setup.
          </p>
        </section>
      </main>
    );
  return (
    <div className="app-shell">
      <aside>
        <div className="brand">
          <span className="brand-icon">n</span>
          <span>
            Notification
            <br />
            Studio
          </span>
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav aria-label="Main navigation">
          {[
            ...(user.is_staff
              ? [["templates", "▦", "Notification settings"]]
              : []),
            ["activity", "◷", "Delivery activity"],
            ["profile", "◎", "My profile"],
          ].map(([key, icon, label]) => (
            <button
              key={key}
              className={tab === key ? "active" : ""}
              onClick={() => setTab(key)}
            >
              <span>{icon}</span>
              {label}
            </button>
          ))}
        </nav>
        <div className="aside-bottom">
          <span className="avatar">
            {user.username.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <strong>{user.username}</strong>
            <small>{user.is_staff ? "Administrator" : "Member"}</small>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header>
          <span>
            Workspace{" "}
            <span className="muted">
              /{" "}
              {tab === "templates"
                ? "Notification settings"
                : tab === "profile"
                  ? "My profile"
                  : "Delivery activity"}
            </span>
          </span>
          <div className="header-actions">
            <Badge tone={config?.dry_run ? "amber" : "green"}>
              {config?.dry_run ? "Dry run" : "Sandbox delivery"}
            </Badge>
            <button className="secondary" disabled={busy} onClick={logout}>
              Log out ↗
            </button>
          </div>
        </header>
        <main className="content">
          {message}
          {config?.dry_run && (
            <p className="mode-note">
              Dry run is enabled. Sends are simulated and do not reach WhatsApp,
              email, or a browser.
            </p>
          )}
          {!config?.dry_run && config?.whatsapp_dry_run && (
            <p className="mode-note">WhatsApp is simulated. Email and Web Push use real sandbox delivery.</p>
          )}
          {tab === "templates" && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">Communication controls</span>
                  <h1>Notification settings</h1>
                  <p className="muted">
                    The right message, at the right moment. All managed in one
                    place.
                  </p>
                </div>
                <button onClick={() => setNewTrigger(true)} disabled={busy}>
                  + Add trigger
                </button>
              </div>
              <div className="stats">
                <div>
                  <span>Event triggers</span>
                  <strong>{triggers.length.toString().padStart(2, "0")}</strong>
                  <small>Connected website moments</small>
                </div>
                <div>
                  <span>Enabled templates</span>
                  <strong>{enabled.toString().padStart(2, "0")}</strong>
                  <small>Across your notification channels</small>
                </div>
                <div>
                  <span>Delivery channels</span>
                  <strong>03</strong>
                  <small>WhatsApp · Email · Web Push</small>
                </div>
              </div>
              <section className="table-panel">
                <div className="table-toolbar">
                  <div>
                    <h2>Trigger library</h2>
                    <p className="muted">
                      Create, edit, sync, and test each message.
                    </p>
                  </div>
                  <input
                    aria-label="Search triggers"
                    placeholder="Search triggers…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <div className="table-scroll">
                  <table className="trigger-table">
                    <thead>
                      <tr>
                        <th>Trigger</th>
                        {channels.map((c) => (
                          <th key={c.key}>
                            <span className={"channel-icon " + c.key}>
                              {c.icon}
                            </span>
                            {c.name}
                            <small>{c.note}</small>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {triggers
                        .filter((t) =>
                          (t.name + t.key)
                            .toLowerCase()
                            .includes(search.toLowerCase()),
                        )
                        .map((t) => (
                          <tr key={t.id}>
                            <td className="trigger-info">
                              <strong>{t.name}</strong>
                              <code>{t.key}</code>
                              <p>{t.description}</p>
                              <label className="check small">
                                <input
                                  type="checkbox"
                                  checked={t.enabled}
                                  disabled={busy}
                                  onChange={() =>
                                    action(async () => {
                                      await api("/triggers/" + t.id + "/", {
                                        method: "PATCH",
                                        body: { enabled: !t.enabled },
                                      });
                                      await refreshTriggers();
                                    })
                                  }
                                />
                                Trigger enabled
                              </label>
                              {!["login", "logout"].includes(t.key) && (
                                <button
                                  className="text-button"
                                  disabled={busy}
                                  onClick={() =>
                                    action(async () => {
                                      const result = await api(
                                        "/triggers/" + t.id + "/fire/",
                                        {
                                          method: "POST",
                                          headers: {
                                            "Idempotency-Key":
                                              crypto.randomUUID(),
                                          },
                                        },
                                      );
                                      notify(describeDeliveries(result));
                                    })
                                  }
                                >
                                  Fire demo event →
                                </button>
                              )}
                            </td>
                            {channels.map((c) => {
                              const template = t.templates.find(
                                (v) => v.channel === c.key,
                              );
                              return (
                                <td key={c.key}>
                                  {template ? (
                                    <div className="template-cell">
                                      <div className="cell-top">
                                        <Badge
                                          tone={template.enabled ? "green" : ""}
                                        >
                                          {template.enabled ? "Enabled" : "Off"}
                                        </Badge>
                                        <button
                                          type="button"
                                          role="switch"
                                          aria-checked={template.enabled}
                                          aria-label={
                                            t.name + " " + c.name + " enabled"
                                          }
                                          className={
                                            "switch " +
                                            (template.enabled ? "on" : "")
                                          }
                                          disabled={busy}
                                          onClick={() => toggle(template)}
                                        >
                                          <span />
                                        </button>
                                      </div>
                                      <strong>
                                        {template.title || "Message template"}
                                      </strong>
                                      <p className="template-body">
                                        {template.body}
                                      </p>
                                      {c.key === "whatsapp" && (
                                        <span className="approval">
                                          Approval:{" "}
                                          {template.provider_status.toLowerCase()}
                                        </span>
                                      )}
                                      <div className="cell-actions">
                                        <button
                                          className="text-button"
                                          disabled={busy}
                                          onClick={() =>
                                            setEditor({
                                              trigger: t,
                                              channel: c.key,
                                              template,
                                            })
                                          }
                                        >
                                          Edit
                                        </button>
                                        {c.key === "whatsapp" && (
                                          <button
                                            className="text-button"
                                            disabled={busy}
                                            onClick={() => sync(template)}
                                          >
                                            Sync
                                          </button>
                                        )}
                                        <button
                                          className="text-button"
                                          disabled={
                                            busy ||
                                            !template.enabled ||
                                            !t.enabled
                                          }
                                          onClick={() => test(template)}
                                        >
                                          Test send ↗
                                        </button>
                                      </div>
                                    </div>
                                  ) : (
                                    <button
                                      className="create-template"
                                      disabled={busy}
                                      onClick={() =>
                                        setEditor({
                                          trigger: t,
                                          channel: c.key,
                                        })
                                      }
                                    >
                                      + Create template
                                    </button>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
                {!triggers.length && (
                  <p className="empty">
                    No triggers yet. Add your first trigger or run the seed_demo
                    command.
                  </p>
                )}
                <div className="table-footer">
                  <span>● Changes are saved per channel</span>
                  <span>Test sends use your notification profile</span>
                </div>
              </section>
            </>
          )}
          {tab === "profile" && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">Recipient setup</span>
                  <h1>My profile</h1>
                  <p className="muted">
                    Choose where your test notifications arrive.
                  </p>
                </div>
              </div>
              <Profile
                user={user}
                config={config}
                saved={setUser}
                notify={notify}
                busy={busy}
                action={action}
              />
            </>
          )}
          {tab === "activity" && (
            <>
              <div className="page-heading">
                <div>
                  <span className="eyebrow">Delivery visibility</span>
                  <h1>Delivery activity</h1>
                  <p className="muted">
                    Accepted means the provider received the request; confirm
                    receipt on your device.
                  </p>
                </div>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => action(refreshLogs)}
                >
                  Refresh
                </button>
              </div>
              <section className="table-panel">
                <div className="table-toolbar">
                  <h2>Notification attempts</h2>
                  <select
                    aria-label="Filter status"
                    value={logFilter}
                    onChange={(e) => {
                      setLogFilter(e.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="">All statuses</option>
                    {[
                      "queued",
                      "sending",
                      "accepted",
                      "simulated",
                      "failed",
                      "skipped",
                    ].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Event</th>
                        <th>Channel / recipient</th>
                        <th>Status</th>
                        <th>Details</th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logs.results.map((log) => (
                        <tr key={log.id}>
                          <td>
                            <strong>{log.trigger}</strong>
                            <small>
                              {log.username}
                              {log.is_test ? " · Test" : ""}
                            </small>
                          </td>
                          <td>
                            {log.channel}
                            <small>{log.recipient || "Not configured"}</small>
                          </td>
                          <td>
                            <Badge
                              tone={
                                log.status === "failed"
                                  ? "red"
                                  : log.status === "accepted"
                                    ? "green"
                                    : "amber"
                              }
                            >
                              {log.status}
                            </Badge>
                          </td>
                          <td className="log-detail">
                            {log.detail}
                            <small>{log.provider_message_id}</small>
                          </td>
                          <td>
                            <small>
                              {new Date(log.created_at).toLocaleString()}
                            </small>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!logs.results.length && (
                  <p className="empty">No delivery attempts match this view.</p>
                )}
                <div className="table-footer">
                  <button
                    className="secondary"
                    disabled={!logs.previous || busy}
                    onClick={() => setPage(page - 1)}
                  >
                    Previous
                  </button>
                  <span>Page {page}</span>
                  <button
                    className="secondary"
                    disabled={!logs.next || busy}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                  </button>
                </div>
              </section>
            </>
          )}
          <footer>
            Notification Studio{" "}
            <span>Built for the StarClinch backend assessment</span>
          </footer>
        </main>
      </div>
      {editor && (
        <TemplateEditor
          {...editor}
          close={() => setEditor(null)}
          saved={refreshTriggers}
        />
      )}
      {newTrigger && (
        <NewTrigger
          close={() => setNewTrigger(false)}
          saved={refreshTriggers}
        />
      )}
    </div>
  );
}
