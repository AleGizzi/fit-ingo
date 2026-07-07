import "./flame.css";

/** The signature streak flame. Grows warmer/livelier with the count.
 *  `dim` (e.g. streak at risk or zero) desaturates it. */
export function Flame({ count, dim = false }: { count: number; dim?: boolean }) {
  return (
    <div className={`flame-wrap ${dim ? "flame-dim" : ""}`}>
      <svg viewBox="0 0 64 80" className="flame-svg" aria-hidden>
        <defs>
          <linearGradient id="flameGrad" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#ffb020" />
            <stop offset="55%" stopColor="#ff5a1f" />
            <stop offset="100%" stopColor="#ff2d55" />
          </linearGradient>
        </defs>
        <path
          className="flame-body"
          fill="url(#flameGrad)"
          d="M32 2c3 12-8 16-8 27 0 6 4 9 4 9s-9-2-11-11C10 42 6 52 6 60a26 26 0 0 0 52 0c0-14-10-22-16-30-4-6-6-14-10-28Z"
        />
        <path
          className="flame-core"
          fill="#ffd76a"
          d="M32 34c2 7-5 9-5 16a10 10 0 0 0 20 0c0-7-6-10-9-16-2-4-4-8-6-16Z"
        />
      </svg>
      <span className="flame-count num">{count}</span>
    </div>
  );
}
