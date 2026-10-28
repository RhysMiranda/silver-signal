import { useEffect, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

const API = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const STRATS = [
  { key: "overnight_rule", label: "Overnight rule", color: "#2563eb" },
  { key: "buy_0915", label: "Buy 09:15", color: "#dc2626" },
  { key: "wait_1015", label: "Buy 10:15", color: "#16a34a" },
];
const pct = (x) => (x == null ? "–" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%`);
const bps = (x) => (x == null ? "–" : `${x >= 0 ? "+" : ""}${x.toFixed(1)} bps`);

async function get(path) {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [equity, setEquity] = useState([]);
  const [trades, setTrades] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([get("/summary"), get("/equity"), get("/trades?limit=15")])
      .then(([s, e, t]) => { setSummary(s); setEquity(e); setTrades(t.reverse()); })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <main><h1>silver-signal</h1><p className="err">Can't reach the API at {API} ({error}).</p></main>;
  if (!summary) return <main><h1>silver-signal</h1><p>Loading…</p></main>;

  return (
    <main>
      <header>
        <h1>silver-signal</h1>
        <p>Paper trading SILVERBEES · {summary.sessions} sessions, {summary.from} to {summary.to} · costs included</p>
      </header>

      <section className="tiles">
        {STRATS.map((s) => (
          <div className="tile" key={s.key} style={{ borderColor: s.color }}>
            <span>{s.label}</span>
            <strong>{pct(summary[`${s.key}_total`])}</strong>
            <small>{summary[`${s.key}_days`]} days</small>
          </div>
        ))}
        <div className="tile">
          <span>First-hour gap, last 20 days</span>
          <strong>{bps(summary.first_hour_gap_bps_last20)}</strong>
          <small>all days {bps(summary.first_hour_gap_bps_all)}</small>
        </div>
      </section>

      <section>
        <h2>Growth of ₹1</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={equity}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="date" minTickGap={40} />
            <YAxis domain={["auto", "auto"]} tickFormatter={(v) => v.toFixed(2)} />
            <Tooltip formatter={(v) => v.toFixed(3)} />
            <Legend />
            <ReferenceLine y={1} stroke="#9ca3af" />
            {STRATS.map((s) => (
              <Line key={s.key} dataKey={s.key} name={s.label} stroke={s.color} dot={false} strokeWidth={2} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </section>

      <section>
        <h2>First-hour gap (ETF minus silver, 20-day average)</h2>
        <p className="note">Below zero: the ETF opened rich and gave it back by 10:15. This faded to zero in 2026; the chart shows whether it returns.</p>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={equity}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="date" minTickGap={40} />
            <YAxis tickFormatter={(v) => `${v.toFixed(0)}`} unit=" bps" width={70} />
            <Tooltip formatter={(v) => bps(v)} />
            <ReferenceLine y={0} stroke="#9ca3af" />
            <Line dataKey="gap_bps_20d" name="Gap" stroke="#7c3aed" dot={false} strokeWidth={2} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </section>

      <section>
        <h2>Latest sessions</h2>
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Date</th><th>Forecast</th><th>Signal</th><th>Open→close</th><th>Buy 10:15</th><th>First-hour gap</th></tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.date}>
                  <td>{t.date}</td>
                  <td>{pct(t.pred_ret_oc)}</td>
                  <td>{t.overnight_rule_buys ? "Buy" : "Flat"}</td>
                  <td className={t.ret_oc >= 0 ? "up" : "down"}>{pct(t.ret_oc)}</td>
                  <td className={t.pnl_wait_1015 >= 0 ? "up" : "down"}>{pct(t.pnl_wait_1015)}</td>
                  <td>{t.gap_first_hour == null ? "–" : bps(t.gap_first_hour * 1e4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <footer>Not financial advice. Research and code: github.com/RhysMiranda/silver-signal</footer>
    </main>
  );
}
