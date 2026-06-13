/**
 * Mount test for ResultsTableRow + StudentNameCell.
 * Added in the CQ 7→8 Wave 3 split (refactor/cq8-03-results-table-row).
 * Renders the row inside a <table><tbody> context (required for <tr>) and
 * asserts the key rendered content + badge icons still reach the DOM after
 * StudentNameCell was extracted from the inline <td> block.
 * Uses .toBeTruthy() (no jest-dom setup in this project).
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import { vi, test, expect } from "vitest";

// api.deleteResult is called by the delete button handler — mock it so the
// import resolves cleanly.
vi.mock("../services/api", () => ({
  deleteResult: vi.fn().mockResolvedValue({}),
}));

import ResultsTableRow from "../tabs/results/ResultsTableRow";

const baseProps = {
  r: {
    filename: "alice.docx",
    student_name: "Alice Adams",
    assignment: "Essay 1",
    score: 92,
    letter_grade: "A",
    graded_at: "2026-06-01 10:00",
    is_handwritten: false,
    marker_status: "verified",
    student_email: "alice@example.com",
    student_id: "sid1",
    token_usage: { total_cost_display: "$0.01" },
  },
  originalIndex: 0,
  status: { is_running: false, results: [] },
  setStatus: vi.fn(),
  setEditedResults: vi.fn(),
  studentAccommodations: {},
  config: {},
  setConfig: vi.fn(),
  addToast: vi.fn(),
  autoApproveEmails: false,
  sentEmails: {},
  emailApprovals: {},
  outlookSendStatus: { status: "idle" },
  openReview: vi.fn(),
  sendSingleEmail: vi.fn(),
};

function Wrapper({ children }) {
  return (
    <table>
      <tbody>{children}</tbody>
    </table>
  );
}

test("ResultsTableRow renders student name", () => {
  render(<ResultsTableRow {...baseProps} />, { wrapper: Wrapper });
  expect(screen.getByText("Alice Adams")).toBeTruthy();
});

test("ResultsTableRow renders assignment name cell", () => {
  render(<ResultsTableRow {...baseProps} />, { wrapper: Wrapper });
  expect(screen.getByText("Essay 1")).toBeTruthy();
});

test("ResultsTableRow renders letter grade", () => {
  render(<ResultsTableRow {...baseProps} />, { wrapper: Wrapper });
  expect(screen.getByText("A")).toBeTruthy();
});

test("StudentNameCell renders handwritten badge when is_handwritten=true", () => {
  const props = { ...baseProps, r: { ...baseProps.r, is_handwritten: true } };
  render(<ResultsTableRow {...props} />, { wrapper: Wrapper });
  expect(screen.getByTitle("Handwritten/Scanned Assignment")).toBeTruthy();
});

test("StudentNameCell renders unverified badge when marker_status=unverified", () => {
  const props = { ...baseProps, r: { ...baseProps.r, marker_status: "unverified" } };
  render(<ResultsTableRow {...props} />, { wrapper: Wrapper });
  expect(screen.getByTitle(/UNVERIFIED/)).toBeTruthy();
});

test("StudentNameCell renders config-mismatch badge when config_mismatch=true", () => {
  const props = { ...baseProps, r: { ...baseProps.r, config_mismatch: true } };
  render(<ResultsTableRow {...props} />, { wrapper: Wrapper });
  expect(screen.getByTitle(/CONFIG MISMATCH/)).toBeTruthy();
});

test("StudentNameCell renders accommodations badge when student has accommodations", () => {
  const props = {
    ...baseProps,
    studentAccommodations: {
      sid1: { presets: [{ name: "Extended Time" }] },
    },
  };
  render(<ResultsTableRow {...props} />, { wrapper: Wrapper });
  expect(screen.getByTitle("Accommodations: Extended Time")).toBeTruthy();
});
