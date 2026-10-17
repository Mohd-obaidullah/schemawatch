import { describe, it, expect } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import { AlertsPage } from "@/pages/AlertsPage";

describe("AlertsPage Filtering", () => {
  it("renders alerts and filters by severity chip", async () => {
    sessionStorage.setItem("schemawatch_bearer_token", "test-token");
    renderWithProviders(<AlertsPage />);

    // Initially loads unacknowledged alerts (stripe amount, twilio status)
    expect(await screen.findByText("$.amount")).toBeInTheDocument();
    expect(screen.getByText("$.status")).toBeInTheDocument();

    // Click "breaking" chip
    const breakingBtn = screen.getByRole("button", { name: /^breaking$/i });
    fireEvent.click(breakingBtn);

    // Should still show breaking alert
    expect(await screen.findByText("$.amount")).toBeInTheDocument();

    // Now click "warning" chip
    const warningBtn = screen.getByRole("button", { name: /^warning$/i });
    fireEvent.click(warningBtn);

    // Should show warning alert
    expect(await screen.findByText("$.status")).toBeInTheDocument();
  });

  it("toggles acknowledged alerts", async () => {
    sessionStorage.setItem("schemawatch_bearer_token", "test-token");
    renderWithProviders(<AlertsPage />);

    // Check include acknowledged checkbox
    const checkbox = await screen.findByLabelText(/Include Acknowledged/i);
    expect(checkbox).not.toBeChecked();

    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();

    // Acknowledged alert $.fee should appear
    expect(await screen.findByText("$.fee")).toBeInTheDocument();
  });
});
