import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

// Analytics header: title, period/quarter filters, district-report export.
// Verbatim from the AnalyticsTab render (CQ wave 1 split).
function AnalyticsFiltersHeader({
  sortedPeriods, analyticsClassPeriod, setAnalyticsClassPeriod,
  analyticsPeriod, setAnalyticsPeriod, filteredAnalytics, addToast,
}) {
  return (
    <div
      data-tutorial="analytics-filters"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: "20px",
      }}
    >
      <h2
        style={{
          fontSize: "1.3rem",
          fontWeight: 700,
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <Icon name="BarChart3" size={24} />
        Class Analytics
      </h2>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "15px",
        }}
      >
        {/* Period Filter */}
        {sortedPeriods.length > 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <label
              style={{
                fontSize: "0.9rem",
                color: "var(--text-secondary)",
              }}
            >
              Period:
            </label>
            <select
              value={analyticsClassPeriod}
              onChange={(e) =>
                setAnalyticsClassPeriod(e.target.value)
              }
              className="input"
              style={{ width: "auto" }}
            >
              <option value="">All Periods</option>
              {sortedPeriods.map((p) => (
                <option key={p.filename} value={p.filename}>
                  {p.period_name}
                </option>
              ))}
            </select>
          </div>
        )}
        {/* Quarter Filter */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <label
            style={{
              fontSize: "0.9rem",
              color: "var(--text-secondary)",
            }}
          >
            Quarter:
          </label>
          <select
            value={analyticsPeriod}
            onChange={(e) =>
              setAnalyticsPeriod(e.target.value)
            }
            className="input"
            style={{ width: "auto" }}
          >
            <option value="all">All Quarters</option>
            {(filteredAnalytics.available_periods || []).map(
              (p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ),
            )}
          </select>
        </div>
        {/* Export District Report Button */}
        <button
          className="btn btn-secondary"
          onClick={async () => {
            try {
              const report = await api.exportDistrictReport();
              if (report.error) {
                addToast(report.error, "error");
                return;
              }
              const blob = new Blob(
                [JSON.stringify(report, null, 2)],
                { type: "application/json" },
              );
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `district_report_${new Date().toISOString().split("T")[0]}.json`;
              a.click();
              URL.revokeObjectURL(url);
            } catch (err) {
              addToast(
                "Failed to export report: " + err.message,
                "error",
              );
            }
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <Icon name="Download" size={16} />
          Export District Report
        </button>
      </div>
    </div>
  );
}

export default AnalyticsFiltersHeader;
