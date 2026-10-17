import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import { OverviewPage } from "@/pages/OverviewPage";

describe("OverviewPage Stat Cards", () => {
  it("renders stat cards with counts fetched from /api/stats", async () => {
    sessionStorage.setItem("schemawatch_bearer_token", "test-token");
    renderWithProviders(<OverviewPage />);

    // Total endpoints
    expect(await screen.findByText("Monitored Endpoints")).toBeInTheDocument();
    expect(await screen.findByText("4")).toBeInTheDocument();

    // Breaking alerts
    expect(screen.getByText("Breaking Alerts")).toBeInTheDocument();

    // Warning alerts
    expect(screen.getByText("Warning Alerts")).toBeInTheDocument();

    // Informational alerts
    expect(screen.getByText("Informational")).toBeInTheDocument();
  });
});
