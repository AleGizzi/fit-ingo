import { weekdayShort } from "../lib/format";
import "./weekring.css";

type DayState = "done" | "today" | "rest" | "missed" | "future";

/** A 7-dot week strip. Filled dots = completed training days. */
export function WeekRing({
  states,
  lang,
}: {
  states: DayState[]; // length 7, Mon..Sun
  lang: string;
}) {
  const labels = weekdayShort(lang);
  return (
    <div className="weekring">
      {states.map((s, i) => (
        <div className="weekring-col" key={i}>
          <div className={`weekring-dot wr-${s}`}>
            {s === "done" ? "✓" : s === "rest" ? "·" : ""}
          </div>
          <span className="weekring-lbl">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}

export type { DayState };
