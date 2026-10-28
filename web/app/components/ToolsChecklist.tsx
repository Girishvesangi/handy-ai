"use client";

import { useState } from "react";
import type { GuideInfo } from "../lib/types";

/** "Before you start": the guide's tools, difficulty and time, with tick boxes. */
export default function ToolsChecklist({ guide }: { guide: GuideInfo }) {
  const [have, setHave] = useState<Set<number>>(new Set());
  const [open, setOpen] = useState(true);
  const facts = [guide.difficulty, guide.time_required].filter(Boolean).join(" · ");

  return (
    <details className="tools" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>
        Before you start
        {guide.tools.length > 0 && (
          <span className="muted">
            {" "}
            ({have.size}/{guide.tools.length} tools ready)
          </span>
        )}
      </summary>
      {facts && <p className="muted">{facts}</p>}
      <p className="safety">Shut down the laptop and unplug the charger first.</p>
      {guide.tools.length > 0 ? (
        <ul>
          {guide.tools.map((tool, i) => (
            <li key={tool + i}>
              <label>
                <input
                  type="checkbox"
                  checked={have.has(i)}
                  onChange={() =>
                    setHave((s) => {
                      const next = new Set(s);
                      if (next.has(i)) next.delete(i);
                      else next.add(i);
                      return next;
                    })
                  }
                />{" "}
                {tool}
              </label>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">This guide doesn&apos;t list specific tools.</p>
      )}
    </details>
  );
}
