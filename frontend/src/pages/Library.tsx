import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useApp } from "../AppContext";
import { api } from "../lib/api";
import { Card, Segmented } from "../components/ui";
import { exInstructions, exName } from "../lib/format";
import type { Exercise } from "../lib/types";
import "./library.css";

type TypeFilter = "all" | Exercise["type"];

const TYPES: TypeFilter[] = ["all", "strength", "cardio", "mobility", "stretch", "balance"];

export function Library() {
  const { t, i18n } = useTranslation();
  const { reload } = useApp();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftUrl, setDraftUrl] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    api.getExercises().then(setExercises).catch(() => setExercises([]));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return exercises.filter((ex) => {
      if (typeFilter !== "all" && ex.type !== typeFilter) return false;
      if (!q) return true;
      const name = exName(ex, i18n.language).toLowerCase();
      return name.includes(q);
    });
  }, [exercises, typeFilter, query, i18n.language]);

  function startEdit(ex: Exercise) {
    setEditingId(ex.id);
    setDraftUrl(ex.video_url ?? "");
  }

  function cancelEdit() {
    setEditingId(null);
    setDraftUrl("");
  }

  async function saveEdit(ex: Exercise) {
    setSavingId(ex.id);
    try {
      await api.patchExerciseVideo(ex.id, draftUrl);
      setExercises((prev) =>
        prev.map((e) => (e.id === ex.id ? { ...e, video_url: draftUrl } : e)),
      );
      await reload();
      setEditingId(null);
      setDraftUrl("");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <div>
          <span className="eyebrow">{t("app.name")}</span>
          <h1 className="page-title">{t("library.title")}</h1>
        </div>
      </header>

      <input
        className="text-input"
        placeholder={t("library.search") ?? ""}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      <div className="lib-filter-scroll">
        <Segmented<TypeFilter>
          value={typeFilter}
          onChange={setTypeFilter}
          options={TYPES.map((ty) => ({ value: ty, label: t(`library.type.${ty}`) }))}
        />
      </div>

      {filtered.length === 0 && (
        <p className="muted">{t("library.empty")}</p>
      )}

      <div className="stack">
        {filtered.map((ex) => (
          <Card key={ex.id} className="lib-card">
            <div className="lib-card-head">
              <h3 className="lib-name">{exName(ex, i18n.language)}</h3>
              <div className="lib-tags">
                <span className="lib-tag">{t(`library.type.${ex.type}`)}</span>
                {ex.impact && <span className="lib-tag">{ex.impact}</span>}
                {ex.equipment && <span className="lib-tag">{ex.equipment}</span>}
              </div>
            </div>
            <p className="lib-instructions">{exInstructions(ex, i18n.language)}</p>

            <div className="lib-actions">
              {ex.video_url && (
                <a className="lib-video" href={ex.video_url} target="_blank" rel="noreferrer">
                  ▶ {t("workout.watch")}
                </a>
              )}
              {editingId !== ex.id && (
                <button className="lib-edit-btn" onClick={() => startEdit(ex)}>
                  {t("common.edit")}
                </button>
              )}
            </div>

            {editingId === ex.id && (
              <div className="lib-edit-row">
                <input
                  className="text-input"
                  value={draftUrl}
                  onChange={(e) => setDraftUrl(e.target.value)}
                  placeholder="https://…"
                />
                <div className="lib-edit-actions">
                  <button className="lib-edit-cancel" onClick={cancelEdit}>
                    {t("common.cancel")}
                  </button>
                  <button
                    className="lib-edit-save"
                    onClick={() => saveEdit(ex)}
                    disabled={savingId === ex.id}
                  >
                    {savingId === ex.id ? t("common.loading") : t("common.save")}
                  </button>
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
