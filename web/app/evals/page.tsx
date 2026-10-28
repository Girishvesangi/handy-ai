"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

// Written by `python -m evals all` in agent/ (see agent/evals/__main__.py).
type Retrieval = { n: number; "hit@1": number; "hit@3": number; mrr: number };
type Report = {
  n: number;
  accuracy: number;
  false_alarm_rate: number;
  mistake_catch_rate: number;
  latency_ms: { p50: number; p95: number };
};
type Results = {
  generated_at: string;
  retrieval?: { guides: number; queries_answerable: number; keyword: Retrieval; hybrid?: Retrieval };
  steps?: { real?: Report; real_without_reference?: Report; proxy?: Report };
  stats?: {
    sessions: number;
    checks: number;
    guides_started: number;
    guides_finished: number;
    check_latency_ms: { p50: number; p95: number };
  };
};

const pct = (x: number) => `${Math.round(x * 100)}%`;

export default function Evals() {
  const [results, setResults] = useState<Results | null | undefined>(undefined);

  useEffect(() => {
    fetch("/eval-results.json")
      .then((r) => (r.ok ? r.json() : null))
      .then(setResults)
      .catch(() => setResults(null));
  }, []);

  return (
    <main className="evals">
      <Link href="/" className="muted">
        ← Back
      </Link>
      <h1>How well does Handy work?</h1>
      <p>
        Measured with the eval harness in <code>agent/evals</code>. Real step checks use labeled phone photos of
        actual repairs; the proxy set uses iFixit&apos;s own photos and only tests photo-to-step matching.
      </p>

      {results === undefined && <p>Loading…</p>}
      {results === null && (
        <p className="hint">
          No results yet. Run <code>python -m evals all --proxy 40</code> in <code>agent/</code>.
        </p>
      )}

      {results?.retrieval && (
        <section>
          <h2>Finding the right guide</h2>
          <p className="muted">
            {results.retrieval.queries_answerable} spoken-style queries over {results.retrieval.guides} guides
          </p>
          <table>
            <thead>
              <tr>
                <th>Search</th>
                <th>Top 1</th>
                <th>Top 3</th>
                <th>MRR</th>
              </tr>
            </thead>
            <tbody>
              {(["keyword", "hybrid"] as const).map((mode) => {
                const r = results.retrieval?.[mode];
                return r ? (
                  <tr key={mode}>
                    <td>{mode === "keyword" ? "Keyword (BM25)" : "Hybrid (BM25 + embeddings)"}</td>
                    <td>{pct(r["hit@1"])}</td>
                    <td>{pct(r["hit@3"])}</td>
                    <td>{r.mrr.toFixed(2)}</td>
                  </tr>
                ) : null;
              })}
            </tbody>
          </table>
        </section>
      )}

      {results?.steps && (
        <section>
          <h2>Checking each step</h2>
          <table>
            <thead>
              <tr>
                <th>Test set</th>
                <th>Cases</th>
                <th>Accuracy</th>
                <th>Mistakes caught</th>
                <th>False alarms</th>
                <th>Latency p50 / p95</th>
              </tr>
            </thead>
            <tbody>
              {(
                [
                  ["real", "Real photos, with reference"],
                  ["real_without_reference", "Real photos, no reference"],
                  ["proxy", "Proxy (iFixit photos)"],
                ] as const
              ).map(([key, label]) => {
                const r = results.steps?.[key];
                return r ? (
                  <tr key={key}>
                    <td>{label}</td>
                    <td>{r.n}</td>
                    <td>{pct(r.accuracy)}</td>
                    <td>{key === "proxy" ? "n/a" : pct(r.mistake_catch_rate)}</td>
                    <td>{key === "proxy" ? "n/a" : pct(r.false_alarm_rate)}</td>
                    <td>
                      {(r.latency_ms.p50 / 1000).toFixed(1)}s / {(r.latency_ms.p95 / 1000).toFixed(1)}s
                    </td>
                  </tr>
                ) : null;
              })}
            </tbody>
          </table>
        </section>
      )}

      {results?.stats && (
        <section>
          <h2>Real sessions</h2>
          <p>
            {results.stats.sessions} sessions, {results.stats.guides_started} guides started,{" "}
            {results.stats.guides_finished} finished, {results.stats.checks} step checks (median{" "}
            {(results.stats.check_latency_ms.p50 / 1000).toFixed(1)}s).
          </p>
        </section>
      )}

      {results && <p className="muted">Last run: {results.generated_at}</p>}
    </main>
  );
}
