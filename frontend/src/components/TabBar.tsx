import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "./tabbar.css";

const tabs = [
  { to: "/today", key: "today", icon: "🔥" },
  { to: "/library", key: "library", icon: "📚" },
  { to: "/progress", key: "progress", icon: "📈" },
  { to: "/diet", key: "diet", icon: "🥗" },
  { to: "/settings", key: "settings", icon: "⚙️" },
];

export function TabBar() {
  const { t } = useTranslation();
  return (
    <nav className="tabbar" aria-label="Primary">
      {tabs.map((tab) => (
        <NavLink
          key={tab.key}
          to={tab.to}
          className={({ isActive }) => `tab ${isActive ? "tab-on" : ""}`}
        >
          <span className="tab-icon" aria-hidden>{tab.icon}</span>
          <span className="tab-label">{t(`nav.${tab.key}`)}</span>
        </NavLink>
      ))}
    </nav>
  );
}
