/**
 * ResultsTable mount test — added as render-equivalence net for the CQ wave-3
 * split that extracted ResultsTableHeader from ResultsTable (207→171 LOC).
 * Protocol-FE requires a mount test when none previously exists.
 *
 * Renders with representative props that exercise both column-config paths
 * (colWidths=null → percent colgroup) and a row in the tbody, asserting
 * the key structural elements are present.
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ResultsTable from "../tabs/results/ResultsTable";

vi.mock("../services/api", () => ({}));

const baseStatus = {
  results: [
    {
      filename: "alice.docx",
      student_name: "Alice Adams",
      assignment: "Essay 1",
      period: "Period 1",
      score: 90,
      letter_grade: "A",
      total_points: 100,
      cost: 0.01,
      authenticity_score: 95,
      graded_at: "2026-06-01T10:00:00Z",
      is_handwritten: false,
      marker_status: "verified",
    },
  ],
};

const defaultProps = {
  editedResults: [],
  status: baseStatus,
  setStatus: vi.fn(),
  setEditedResults: vi.fn(),
  resultsFilter: "all",
  emailApprovals: {},
  resultsPeriodFilter: "",
  resultsAssignmentFilter: "",
  resultsSearch: "",
  resultsSort: { field: "time", direction: "desc" },
  colWidths: null,
  defaultColPercents: [14, 20, 10, 8, 7, 7, 10, 8, 16],
  tableRef: { current: null },
  initColWidths: vi.fn(),
  handleResizeStart: vi.fn(),
  theme: "light",
  studentAccommodations: {},
  config: {},
  setConfig: vi.fn(),
  addToast: vi.fn(),
  autoApproveEmails: false,
  sentEmails: {},
  outlookSendStatus: {},
  openReview: vi.fn(),
  sendSingleEmail: vi.fn(),
};

describe("ResultsTable mount", () => {
  it("renders the table with header columns and a student row", () => {
    render(<ResultsTable {...defaultProps} />);
    // Header columns present (from ResultsTableHeader child)
    expect(screen.getByRole("columnheader", { name: "Student" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Assignment" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Score" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Actions" })).toBeTruthy();
    // Student row rendered
    expect(screen.getByText("Alice Adams")).toBeTruthy();
  });

  it("renders with colWidths (pixel colgroup path)", () => {
    const widths = [120, 180, 90, 70, 65, 65, 95, 75, 140];
    render(<ResultsTable {...defaultProps} colWidths={widths} />);
    expect(screen.getByRole("columnheader", { name: "Student" })).toBeTruthy();
  });
});
