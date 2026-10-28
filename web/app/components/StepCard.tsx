"use client";

import { useState } from "react";
import type { GuideState } from "../lib/types";

type Active = Exclude<GuideState, { guide: null }>;

export default function StepCard({ state }: { state: Active }) {
  const { guide, step, completed } = state;
  const [zoomed, setZoomed] = useState(false);
  const photo = step.image_urls[0];
  const progress = (completed.length / guide.total_steps) * 100;

  return (
    <section className="step-card" aria-live="polite">
      <div className="step-head">
        <a href={guide.url} target="_blank" rel="noreferrer" className="guide-title">
          {guide.title}
        </a>
        <span className="step-count">
          Step {step.number} of {guide.total_steps}
        </span>
      </div>
      <div className="progress" aria-hidden>
        <div style={{ width: `${progress}%` }} />
      </div>
      <div className="step-body">
        {photo && (
          <button className="thumb" onClick={() => setZoomed(true)} aria-label="Enlarge reference photo">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={photo} alt={`Reference photo for step ${step.number}`} />
          </button>
        )}
        <div>
          {step.title && <h2>{step.title}</h2>}
          <ul>
            {step.lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      </div>
      <p className="credit">
        Guide from{" "}
        <a href={guide.url} target="_blank" rel="noreferrer">
          iFixit
        </a>{" "}
        (CC BY-NC-SA)
      </p>
      {zoomed && photo && (
        <button className="zoom" onClick={() => setZoomed(false)} aria-label="Close photo">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={photo} alt={`Reference photo for step ${step.number}`} />
        </button>
      )}
    </section>
  );
}
