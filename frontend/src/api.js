export const API_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000/api"
).replace(/\/$/, "");
export async function api(path, { method = "GET", body, headers = {} } = {}) {
  const token = sessionStorage.getItem("notification_token");
  let response;
  try {
    response = await fetch(API_URL + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: "Token " + token } : {}),
        ...headers,
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new Error(
      "Cannot reach the backend. Check the server and VITE_API_URL.",
    );
  }
  const data =
    response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login/") {
      sessionStorage.removeItem("notification_token");
      window.dispatchEvent(new Event("session-expired"));
    }
    throw new Error(
      data?.detail ||
        (data
          ? Object.entries(data)
              .map(
                ([k, v]) =>
                  k +
                  ": " +
                  (Array.isArray(v) ? v.join(", ") : JSON.stringify(v)),
              )
              .join(" · ")
          : "Request failed (" + response.status + ")."),
    );
  }
  return data;
}
export function describeDeliveries(data) {
  const items = data.deliveries || [];
  if (!items.length) return "Event recorded. No templates are configured.";
  return items
    .map(
      (d) => d.channel + ": " + d.status + (d.detail ? " — " + d.detail : ""),
    )
    .join("\n");
}
