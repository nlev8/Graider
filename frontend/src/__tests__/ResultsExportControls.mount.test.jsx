import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ResultsExportControls from "../tabs/results/ResultsExportControls";

// Added in CQ wave-3 alongside extraction of ExportEmailActionsGroup.
// Renders ResultsExportControls with representative props so a missed prop
// or broken import surfaces here instead of in the nightly e2e.

vi.mock("../services/api", () => ({
  uploadFocusComments: vi.fn().mockResolvedValue({ total: 1 }),
  exportOutlookEmails: vi.fn().mockResolvedValue({ count: 1, emails: [] }),
  sendOutlookEmails: vi.fn().mockResolvedValue({ total: 1 }),
  sendFocusComms: vi.fn().mockResolvedValue({ total: 1 }),
  sendFileConfirmations: vi.fn().mockResolvedValue({ total: 1, sent_filenames: [] }),
}));

vi.mock("../tabs/results/ExportGradesDropdown", () => ({
  default: () => <button>Export Grades</button>,
}));

const baseProps = {
  gradesApproved: true,
  batchExportLoading: false,
  setBatchExportLoading: vi.fn(),
  editedResults: [],
  status: {
    results: [{ filename: "a1.docx", assignment: "Essay 1" }],
    is_running: false,
    complete: true,
    log: [],
  },
  resultsAssignmentFilter: "",
  resultsPeriodFilter: "",
  setResultsPeriodFilter: vi.fn(),
  setFocusExportModal: vi.fn(),
  addToast: vi.fn(),
  config: {
    sis_type: "focus",
    assignments_folder: "/tmp/assignments",
    teacher_name: "Ms. Test",
    email_signature: "Ms. Test",
  },
  focusCommentsStatus: { status: "idle", entered: 0, total: 0, failed: 0, message: "" },
  setFocusCommentsStatus: vi.fn(),
  setFocusCommentsPolling: vi.fn(),
  vportalConfigured: true,
  outlookExportLoading: false,
  setOutlookExportLoading: vi.fn(),
  outlookSendStatus: { status: "idle", sent: 0, total: 0, failed: 0, message: "" },
  setOutlookSendStatus: vi.fn(),
  setOutlookSendPolling: vi.fn(),
  focusCommsStatus: { status: "idle", sent: 0, total: 0, failed: 0, skipped: 0, message: "" },
  setFocusCommsStatus: vi.fn(),
  setFocusCommsPolling: vi.fn(),
  sortedPeriods: [{ filename: "p1.csv", period_name: "Period 1" }],
  setConfirmationStudentFilter: vi.fn(),
  confirmationStudentFilter: "",
  pendingConfirmationStudents: ["Alice Adams"],
  pendingConfirmations: 2,
  pendingConfirmationFilenames: { current: [] },
  ccParents: false,
  setCcParents: vi.fn(),
};

describe("ResultsExportControls (post ExportEmailActionsGroup extraction)", () => {
  it("renders export grades and upload comments buttons", () => {
    render(<ResultsExportControls {...baseProps} />);
    expect(screen.getByText("Export Grades")).toBeTruthy();
    expect(screen.getByText("Upload Comments")).toBeTruthy();
  });

  it("renders email action buttons when sis_type is focus", () => {
    render(<ResultsExportControls {...baseProps} />);
    expect(screen.getByText("Parent Emails")).toBeTruthy();
    expect(screen.getByText("Send via Focus")).toBeTruthy();
    expect(screen.getByText("Send via Outlook")).toBeTruthy();
  });

  it("does not render email action buttons when sis_type is not focus", () => {
    render(
      <ResultsExportControls
        {...baseProps}
        config={{ ...baseProps.config, sis_type: "clever" }}
      />
    );
    expect(screen.queryByText("Parent Emails")).toBeNull();
    expect(screen.queryByText("Send via Focus")).toBeNull();
  });

  it("renders confirmation group when assignments_folder is set", () => {
    render(<ResultsExportControls {...baseProps} />);
    expect(screen.getByText("Send Confirmations (2)")).toBeTruthy();
    expect(screen.getByText("CC Parents")).toBeTruthy();
    // Period filter select rendered when sortedPeriods is non-empty
    expect(screen.getByText("All Periods")).toBeTruthy();
  });

  it("does not render confirmation group when assignments_folder is absent", () => {
    render(
      <ResultsExportControls
        {...baseProps}
        config={{ ...baseProps.config, assignments_folder: "" }}
      />
    );
    expect(screen.queryByText("Send Confirmations (2)")).toBeNull();
  });
});
