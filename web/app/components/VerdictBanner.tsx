"use client";

import type { CheckResult } from "../lib/types";

const LABELS: Record<CheckResult["verdict"], { icon: string; text: string }> = {
  done: { icon: "✓", text: "Looks done" },
  not_done: { icon: "…", text: "Not done yet" },
  wrong: { icon: "!", text: "Something looks wrong" },
  unclear: { icon: "?", text: "Can't tell" },
};

export default function VerdictBanner({ result }: { result: CheckResult }) {
  const { icon, text } = LABELS[result.verdict];
  return (
    <div className={`verdict verdict-${result.verdict}`} role="status">
      <span className="verdict-icon" aria-hidden>
        {icon}
      </span>
      <div>
        <strong>
          {text} <span className="muted">(step {result.step})</span>
        </strong>
        <p>{result.reason}</p>
      </div>
    </div>
  );
}
