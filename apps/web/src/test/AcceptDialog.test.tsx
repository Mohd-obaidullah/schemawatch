import { describe, it, expect } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import { EndpointDetailPage } from "@/pages/EndpointDetailPage";

describe("EndpointDetailPage Accept Dialog", () => {
  it("opens confirmation dialog and accepts new schema baseline", async () => {
    sessionStorage.setItem("schemawatch_bearer_token", "test-token");
    renderWithProviders(<EndpointDetailPage />, {
      initialEntries: ["/endpoints/1"],
    });

    // Wait for endpoint to load
    const acceptBtn = await screen.findByRole("button", {
      name: /accept new schema/i,
    });
    expect(acceptBtn).toBeInTheDocument();

    // Click "Accept New Schema" button to open modal
    fireEvent.click(acceptBtn);

    // Dialog should be visible
    expect(screen.getByText("Accept New Schema Baseline")).toBeInTheDocument();
    expect(
      screen.getByText(/Are you sure you want to adopt the most recently observed payload shape/i)
    ).toBeInTheDocument();

    // Click confirm in dialog
    const confirmBtn = screen.getByRole("button", {
      name: /confirm & adopt baseline/i,
    });
    fireEvent.click(confirmBtn);

    // Dialog should close and toast should trigger
    await waitFor(() => {
      expect(screen.queryByText("Accept New Schema Baseline")).not.toBeInTheDocument();
    });
  });
});
