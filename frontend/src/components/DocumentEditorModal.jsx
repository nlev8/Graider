import React from "react";
import DocEditorHeader from "./document-editor-modal/DocEditorHeader";
import MarkerSidebar from "./document-editor-modal/MarkerSidebar";

export default function DocumentEditorModal(props) {
  const { docEditorModal, docHtmlRef } = props;
  return (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "var(--modal-bg)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <DocEditorHeader {...props} />
          <div
            style={{
              flex: 1,
              display: "grid",
              gridTemplateColumns: "1fr 300px",
              overflow: "hidden",
            }}
          >
            <div style={{ overflow: "auto", padding: "20px" }}>
              <iframe
                ref={docHtmlRef}
                srcDoc={`<!DOCTYPE html><html><head><style>body{font-family:Georgia,serif;padding:40px;background:#fff;color:#000;line-height:1.6}::selection{background:#6366f1;color:#fff}</style></head><body>${docEditorModal.editedHtml}</body></html>`}
                style={{
                  width: "100%",
                  height: "100%",
                  border: "none",
                  borderRadius: "8px",
                  minHeight: "600px",
                }}
              />
            </div>
            <MarkerSidebar {...props} />
          </div>
        </div>
  );
}
