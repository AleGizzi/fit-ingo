import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { Card } from "../components/ui";
import type { DietInfo } from "../lib/types";
import "./diet.css";

const SLOTS = ["breakfast", "lunch", "dinner", "snack"] as const;

export function Diet() {
  const { t, i18n } = useTranslation();
  const [diet, setDiet] = useState<DietInfo | null>(null);

  useEffect(() => {
    api.getDiet().then(setDiet).catch(() => setDiet(null));
  }, []);

  if (!diet) return <p className="muted">{t("common.loading")}</p>;

  const { targets, suggestions } = diet;
  const es = i18n.language === "es";
  const macros = [
    { key: "protein", value: targets.protein_g, unit: "g", accent: "ember" },
    { key: "carbs", value: targets.carb_g, unit: "g", accent: "violet" },
    { key: "fat", value: targets.fat_g, unit: "g", accent: "gold" },
  ];

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("app.name")}</span>
          <h1 className="page-title">{t("diet.targets")}</h1>
        </div>
      </header>

      <Card className="kcal-card">
        <div className="kcal-big num">{targets.kcal}</div>
        <div className="kcal-unit">kcal / {es ? "día" : "day"}</div>
        <div className="kcal-sub">{t("diet.bmrTdee", { bmr: targets.bmr, tdee: targets.tdee })}</div>
      </Card>

      <div className="macro-grid">
        {macros.map((m) => (
          <div className={`macro macro-${m.accent}`} key={m.key}>
            <div className="macro-value num">{m.value}<span className="macro-unit">{m.unit}</span></div>
            <div className="macro-label">{t(`diet.${m.key}`)}</div>
          </div>
        ))}
        <div className="macro macro-water">
          <div className="macro-value num">{(targets.water_ml / 1000).toFixed(1)}<span className="macro-unit">L</span></div>
          <div className="macro-label">{t("diet.water")}</div>
        </div>
      </div>

      <div>
        <span className="eyebrow" style={{ display: "block", margin: "6px 2px 12px" }}>
          {t("diet.meals")}
        </span>
        <div className="stack">
          {SLOTS.map((slot) => {
            const meal = suggestions.meals[slot];
            if (!meal) return null;
            return (
              <Card key={slot} className="meal-card">
                <div className="meal-slot">{t(`diet.${slot}`)}</div>
                <div className="meal-name">{es ? meal.name_es : meal.name_en}</div>
                <div className="meal-macros">
                  <span className="num">{meal.kcal}</span> kcal ·
                  <span className="num"> {meal.protein_g}g</span> {t("diet.protein").toLowerCase()}
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      <div className="spread total-row">
        <span>{t("diet.total")}</span>
        <span className="num">{suggestions.total_kcal} kcal · {suggestions.total_protein_g}g</span>
      </div>

      <p className="disclaimer">{es ? suggestions.note_es : suggestions.note_en}</p>
    </div>
  );
}
