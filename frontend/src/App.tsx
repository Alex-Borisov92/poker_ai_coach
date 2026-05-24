import { useState } from "react";

import { AppShell } from "./layout/AppShell";
import type { NavItem } from "./layout/AppShell";
import { CoachChatPage } from "./pages/CoachChatPage";
import { LeakFinderPage } from "./pages/LeakFinderPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StudyPlanPage } from "./pages/StudyPlanPage";

export default function App() {
  const [activePage, setActivePage] = useState<NavItem>("AI Coach");

  const page =
    activePage === "AI Coach" ? (
      <CoachChatPage />
    ) : activePage === "Settings" ? (
      <SettingsPage />
    ) : activePage === "Leak Finder" ? (
      <LeakFinderPage />
    ) : activePage === "Study Plan" ? (
      <StudyPlanPage />
    ) : (
      <PlaceholderPage title={activePage} />
    );

  return (
    <AppShell activeItem={activePage} onNavigate={setActivePage}>
      {page}
    </AppShell>
  );
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{title}</h1>
          <p>This section is planned for a later milestone.</p>
        </div>
        <div className="status-pill warning">Planned</div>
      </header>
    </div>
  );
}
