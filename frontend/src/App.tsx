import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppProvider, useApp } from "./AppContext";
import { TabBar } from "./components/TabBar";
import { Onboarding } from "./pages/Onboarding";
import { Today } from "./pages/Today";
import { Workout } from "./pages/Workout";
import { QuickSession } from "./pages/QuickSession";
import { Library } from "./pages/Library";
import { Progress } from "./pages/Progress";
import { Diet } from "./pages/Diet";
import { Settings } from "./pages/Settings";
import "./app.css";

function Shell() {
  const { ready, profile } = useApp();
  const location = useLocation();

  if (!ready) {
    return (
      <div className="splash">
        <div className="splash-mark">🔥</div>
      </div>
    );
  }

  // No profile yet -> force onboarding.
  if (!profile && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }

  const showTabs =
    !!profile &&
    location.pathname !== "/onboarding" &&
    !location.pathname.startsWith("/workout") &&
    !location.pathname.startsWith("/quick");

  return (
    <div className="app-shell">
      <main className={`app-main ${showTabs ? "with-tabs" : ""}`}>
        <Routes>
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/today" element={<Today />} />
          <Route path="/workout" element={<Workout />} />
          <Route path="/quick/:kind" element={<QuickSession />} />
          <Route path="/library" element={<Library />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/diet" element={<Diet />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/today" replace />} />
        </Routes>
      </main>
      {showTabs && <TabBar />}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <Shell />
      </AppProvider>
    </BrowserRouter>
  );
}
