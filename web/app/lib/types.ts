// Shapes of the data messages the agent sends (see agent/agent.py).

export type GuideState =
  | { guide: null }
  | {
      guide: { id: number; title: string; device: string; url: string; total_steps: number };
      step: { number: number; title: string; lines: string[]; image_urls: string[] };
      completed: number[];
    };

export type Verdict = "done" | "not_done" | "wrong" | "unclear";

export type CheckResult = {
  verdict: Verdict;
  confidence: number;
  reason: string;
  tip: string;
  latency_ms: number;
  step: number;
};
