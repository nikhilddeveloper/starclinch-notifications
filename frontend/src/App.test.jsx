import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App, { preview } from "./App";
import { api } from "./api";
vi.mock("./api", () => ({
  api: vi.fn(),
  describeDeliveries: (data) =>
    data.deliveries.map((d) => d.channel + ": " + d.status).join(", "),
}));
vi.mock("./push", () => ({ initPush: vi.fn(), subscribe: vi.fn() }));
const user = {
  id: 1,
  username: "nikhil",
  first_name: "Nikhil",
  email: "n@example.com",
  phone: "",
  is_staff: true,
  email_consent: false,
  whatsapp_consent: false,
  push_subscriptions: [],
};
let triggers;
beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
  triggers = [
    {
      id: 1,
      key: "login",
      name: "Login",
      description: "When a user signs in",
      enabled: true,
      templates: [
        {
          id: 2,
          trigger: 1,
          channel: "email",
          title: "Welcome",
          body: "Hello {{name}}",
          variable_mappings: { name: "user.name" },
          enabled: true,
          language: "en_US",
          category: "UTILITY",
        },
      ],
    },
  ];
  api.mockImplementation(async (path, options) => {
    if (path === "/auth/me/") return user;
    if (path === "/config/") return { dry_run: true, onesignal_app_id: "" };
    if (path === "/triggers/") return triggers;
    if (path === "/templates/2/" && options?.method === "PATCH") {
      Object.assign(triggers[0].templates[0], options.body);
      return triggers[0].templates[0];
    }
    if (path === "/templates/2/test/")
      return { deliveries: [{ channel: "email", status: "simulated" }] };
    throw new Error("Unexpected request: " + path);
  });
});
async function admin() {
  sessionStorage.setItem("notification_token", "test");
  render(<App />);
  await screen.findByRole("switch");
}
describe("notification console", () => {
  it("shows login form without a session", () => {
    render(<App />);
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "type",
      "password",
    );
  });
  it("clearly labels dry-run mode", async () => {
    await admin();
    expect(screen.getByText(/Sends are simulated/)).toBeInTheDocument();
  });
  it("renders the required channel table", async () => {
    await admin();
    for (const label of ["WhatsApp", "Email", "Web Push"])
      expect(
        screen.getByRole("columnheader", { name: new RegExp(label) }),
      ).toBeInTheDocument();
  });
  it("persists a toggle and disables test send", async () => {
    await admin();
    await userEvent.click(screen.getByRole("switch"));
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("/templates/2/", {
        method: "PATCH",
        body: { enabled: false },
      }),
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Test send/ })).toBeDisabled(),
    );
  });
  it("edits and saves template content", async () => {
    await admin();
    await userEvent.click(
      screen.getByRole("button", { name: "Edit", exact: true }),
    );
    const body = screen.getByLabelText("Message");
    await userEvent.clear(body);
    await userEvent.type(body, "Updated message");
    await userEvent.click(
      screen.getByRole("button", { name: "Save template" }),
    );
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith(
        "/templates/2/",
        expect.objectContaining({
          method: "PATCH",
          body: expect.objectContaining({ body: "Updated message" }),
        }),
      ),
    );
  });
  it("reports simulated sends without claiming delivery", async () => {
    await admin();
    await userEvent.click(screen.getByRole("button", { name: /Test send/ }));
    expect(await screen.findByText("email: simulated")).toBeInTheDocument();
  });
  it("shows actionable backend errors", async () => {
    await admin();
    api.mockRejectedValueOnce(new Error("Provider timed out"));
    await userEvent.click(screen.getByRole("button", { name: /Test send/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Provider timed out",
    );
  });
  it("renders a safe plain-text variable preview", () => {
    expect(preview("Hello {{name}}", { name: "user.name" })).toBe(
      "Hello Nikhil",
    );
    expect(preview("{{missing}}", {})).toBe("[unmapped: missing]");
  });
});
