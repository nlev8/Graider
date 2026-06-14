/**
 * Mount test for ResultsFilterControls + its extracted child ResultsClearButton.
 * Added as render-equivalence net for the CQ wave-3 split (Protocol-FE).
 * Asserts that the parent renders all visible controls (sort, filter, clear)
 * and that the extracted child mounts without error.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ResultsFilterControls from "../tabs/results/ResultsFilterControls";
import ResultsClearButton from "../tabs/results/ResultsClearButton";

vi.mock("../services/api", () => ({
  clearResults: vi.fn().mockResolvedValue({}),
}));

// Minimal Icon stub — avoids importing lucide-react in test env
vi.mock("../components/Icon", () => ({
  default: ({ name }) => <span data-testid={`icon-${name}`} />,
}));

const baseProps = () => ({
  resultsSort: { field: "time", direction: "desc" },
  setResultsSort: vi.fn(),
  resultsFilter: "all",
  setResultsFilter: vi.fn(),
  portalSubmissions: [],
  sortedPeriods: [],
  resultsPeriodFilter: "",
  setResultsPeriodFilter: vi.fn(),
  savedAssignments: [],
  savedAssignmentData: {},
  resultsAssignmentFilter: "",
  setResultsAssignmentFilter: vi.fn(),
  curveModal: { show: false },
  setCurveModal: vi.fn(),
  resultsSearch: "",
  status: { results: [] },
  setStatus: vi.fn(),
  setEditedResults: vi.fn(),
  emailApprovals: {},
  setEmailApprovals: vi.fn(),
  setEditedEmails: vi.fn(),
  addToast: vi.fn(),
  gradesApproved: false,
  setGradesApproved: vi.fn(),
});

describe("ResultsFilterControls", () => {
  it("renders sort and filter dropdowns", () => {
    render(<ResultsFilterControls {...baseProps()} />);
    expect(screen.getByDisplayValue("Newest First")).toBeTruthy();
    expect(screen.getByDisplayValue("All Results")).toBeTruthy();
  });

  it("renders Clear All button (no active filter)", () => {
    render(<ResultsFilterControls {...baseProps()} />);
    expect(screen.getByText("Clear All")).toBeTruthy();
  });

  it("renders Clear Filtered button when filter is active", () => {
    render(
      <ResultsFilterControls {...baseProps()} resultsFilter="approved" />
    );
    expect(screen.getByText("Clear Filtered")).toBeTruthy();
  });

  it("renders period dropdown when sortedPeriods provided", () => {
    const props = {
      ...baseProps(),
      sortedPeriods: [{ filename: "p1.docx", period_name: "Period 1" }],
    };
    render(<ResultsFilterControls {...props} />);
    expect(screen.getByDisplayValue("All Periods")).toBeTruthy();
  });

  it("renders approval checkbox when results present", () => {
    const props = {
      ...baseProps(),
      status: {
        results: [
          { student_name: "Alice", filename: "alice.docx", marker_status: "unverified" },
        ],
      },
    };
    render(<ResultsFilterControls {...props} />);
    expect(
      screen.getByText(/I have reviewed and approve these grades/i)
    ).toBeTruthy();
  });

  it("does not show Apply Curve without period filter", () => {
    render(<ResultsFilterControls {...baseProps()} />);
    expect(screen.queryByText("Apply Curve")).toBeNull();
  });

  it("shows Apply Curve button when period filter active", () => {
    render(
      <ResultsFilterControls {...baseProps()} resultsPeriodFilter="Period 1" />
    );
    expect(screen.getByText("Apply Curve")).toBeTruthy();
  });
});

describe("ResultsClearButton (child)", () => {
  const clearProps = () => ({
    resultsFilter: "all",
    resultsPeriodFilter: "",
    resultsAssignmentFilter: "",
    resultsSearch: "",
    status: { results: [] },
    emailApprovals: {},
    setStatus: vi.fn(),
    setEditedResults: vi.fn(),
    setEmailApprovals: vi.fn(),
    setEditedEmails: vi.fn(),
    addToast: vi.fn(),
  });

  it("renders Clear All when no filter active", () => {
    render(<ResultsClearButton {...clearProps()} />);
    expect(screen.getByText("Clear All")).toBeTruthy();
  });

  it("renders Clear Filtered when a filter is active", () => {
    render(<ResultsClearButton {...clearProps()} resultsFilter="approved" />);
    expect(screen.getByText("Clear Filtered")).toBeTruthy();
  });
});
