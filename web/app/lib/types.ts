// Shapes of the data messages the agent sends (see agent/agent.py).

export type GuideInfo = {
  id: number;
  title: string;
  device: string;
  url: string;
  total_steps: number;
  tools: string[];
  difficulty: string;
  time_required: string;
};

export type GuideState =
  | { guide: null }
  | {
      guide: GuideInfo;
      step: { number: number; title: string; lines: string[]; image_urls: string[] };
      completed: number[];
    };

export type ActiveGuide = Exclude<GuideState, { guide: null }>;

export type Verdict = "done" | "not_done" | "wrong" | "unclear";

export type CheckResult = {
  verdict: Verdict;
  confidence: number;
  reason: string;
  tip: string;
  latency_ms: number;
  step: number;
};

// Box is [ymin, xmin, ymax, xmax] as fractions of the camera frame.
export type PointerMsg = {
  found: boolean;
  label: string;
  box: number[];
  step: number;
  frame_w: number;
  frame_h: number;
};

export type Recap = {
  guide_id: number;
  title: string;
  url: string;
  total_steps: number;
  steps_completed: number;
  minutes: number;
  checks: number;
  mistakes_caught: { step: number; reason: string }[];
};
