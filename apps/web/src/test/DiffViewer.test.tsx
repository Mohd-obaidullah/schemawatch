import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DiffViewer } from "@/components/diff/DiffViewer";
import type { DriftEvent } from "@/types";

const sampleEvent: DriftEvent = {
  id: 42,
  endpoint_id: 1,
  vendor: "stripe",
  endpoint: "POST /v1/charges",
  field_path: "$.amount",
  kind: "type_changed",
  severity: "breaking",
  was_value: "integer",
  now_value: "string",
  detail: "integer -> string",
  observed_schema: {},
  acknowledged: false,
  acknowledged_at: null,
  detected_at: "2026-10-17T18:00:00Z",
};

describe("DiffViewer Component", () => {
  it("renders field path, was value, now value, and severity badge", () => {
    render(<DiffViewer event={sampleEvent} />);

    expect(screen.getByText("$.amount")).toBeInTheDocument();
    expect(screen.getByText("integer")).toBeInTheDocument();
    expect(screen.getByText("string")).toBeInTheDocument();
    expect(screen.getByText("breaking")).toBeInTheDocument();
    expect(screen.getByText("WAS")).toBeInTheDocument();
    expect(screen.getByText("NOW")).toBeInTheDocument();
    expect(screen.getByText("integer -> string")).toBeInTheDocument();
  });

  it("renders compact mode properly", () => {
    render(<DiffViewer event={sampleEvent} compact={true} />);

    expect(screen.getByText("$.amount:")).toBeInTheDocument();
    expect(screen.getByText("integer")).toBeInTheDocument();
    expect(screen.getByText("string")).toBeInTheDocument();
  });
});
