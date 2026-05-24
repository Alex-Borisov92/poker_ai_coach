import { useState } from "react";

import { LeakFinderPage } from "./LeakFinderPage";
import { OverviewPage } from "./OverviewPage";
import { StudyPlanPage } from "./StudyPlanPage";

type ReportTab = "Overview" | "Leak Finder" | "Study Plan";

const reportTabs: ReportTab[] = ["Overview", "Leak Finder", "Study Plan"];

export function ReportsPage() {
  const [activeTab, setActiveTab] = useState<ReportTab>("Overview");

  return (
    <div className="reports-page">
      <section className="panel report-tabs-panel" aria-label="Report tabs">
        <div className="report-tabs">
          {reportTabs.map((tab) => (
            <button
              className={tab === activeTab ? "report-tab active" : "report-tab"}
              key={tab}
              onClick={() => setActiveTab(tab)}
              type="button"
            >
              {tab}
            </button>
          ))}
        </div>
      </section>
      {activeTab === "Overview" ? <OverviewPage /> : null}
      {activeTab === "Leak Finder" ? <LeakFinderPage /> : null}
      {activeTab === "Study Plan" ? <StudyPlanPage /> : null}
    </div>
  );
}
