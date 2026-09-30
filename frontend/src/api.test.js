import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./api";
beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal("fetch", vi.fn());
});
it("attaches the session token to protected requests", async () => {
  sessionStorage.setItem("notification_token", "sample");
  fetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ ok: true }),
  });
  await api("/auth/me/");
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe("Token sample");
});
it("clears rejected sessions", async () => {
  sessionStorage.setItem("notification_token", "expired");
  fetch.mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({ detail: "Expired" }),
  });
  await expect(api("/auth/me/")).rejects.toThrow("Expired");
  expect(sessionStorage.getItem("notification_token")).toBeNull();
});
it("explains network failures", async () => {
  fetch.mockRejectedValue(new TypeError("Failed to fetch"));
  await expect(api("/triggers/")).rejects.toThrow("Cannot reach the backend");
});
it("handles empty successful delete responses", async () => {
  fetch.mockResolvedValue({ ok: true, status: 204 });
  await expect(
    api("/push-subscriptions/", {
      method: "DELETE",
      body: { subscription_id: "id" },
    }),
  ).resolves.toBeNull();
});
