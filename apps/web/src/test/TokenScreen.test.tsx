import { describe, it, expect } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "./test-utils";
import { TokenPage } from "@/pages/TokenPage";

describe("TokenScreen Component", () => {
  it("renders input, updates value, and saves token to sessionStorage on submit", async () => {
    renderWithProviders(<TokenPage />, { initialEntries: ["/token"] });

    expect(screen.getByText("schemawatch Access")).toBeInTheDocument();
    const input = screen.getByLabelText(/bearer token/i);
    expect(input).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "my-secret-token" } });
    expect(input).toHaveValue("my-secret-token");

    const submitBtn = screen.getByRole("button", { name: /continue to dashboard/i });
    fireEvent.click(submitBtn);

    expect(sessionStorage.getItem("schemawatch_bearer_token")).toBe("my-secret-token");
  });
});
