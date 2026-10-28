"use client";

import type { Recap } from "../lib/types";

export default function RecapCard({ recap, onClose }: { recap: Recap; onClose: () => void }) {
  const done = recap.steps_completed >= recap.total_steps;
  return (
    <div className="recap-backdrop" role="dialog" aria-modal="true" aria-label="Repair recap">
      <section className="recap">
        <h2>{done ? "Repair complete 🎉" : "Repair summary"}</h2>
        <p className="muted">{recap.title}</p>
        <div className="stats">
          <div>
            <strong>
              {recap.steps_completed}/{recap.total_steps}
            </strong>
            <span>steps confirmed</span>
          </div>
          <div>
            <strong>{recap.minutes}</strong>
            <span>minutes</span>
          </div>
          <div>
            <strong>{recap.mistakes_caught.length}</strong>
            <span>{recap.mistakes_caught.length === 1 ? "mistake caught" : "mistakes caught"}</span>
          </div>
        </div>
        {recap.mistakes_caught.length > 0 && (
          <>
            <h3>What Handy caught</h3>
            <ul>
              {recap.mistakes_caught.map((m, i) => (
                <li key={i}>
                  Step {m.step}: {m.reason}
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="muted">
          {recap.checks} camera checks.{" "}
          <a href={recap.url} target="_blank" rel="noreferrer">
            Open the full guide
          </a>
        </p>
        <button onClick={onClose}>Done</button>
      </section>
    </div>
  );
}
