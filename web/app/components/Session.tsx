"use client";

import {
  TrackToggle,
  VideoTrack,
  useDataChannel,
  useLocalParticipant,
  useRoomContext,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { useEffect, useRef, useState } from "react";
import type { CheckResult, GuideState, PointerMsg, Recap } from "../lib/types";
import Captions from "./Captions";
import PointerOverlay from "./PointerOverlay";
import RecapCard from "./RecapCard";
import StepCard from "./StepCard";
import ToolsChecklist from "./ToolsChecklist";
import VerdictBanner from "./VerdictBanner";

const decoder = new TextDecoder();
const parse = <T,>(payload: Uint8Array) => JSON.parse(decoder.decode(payload)) as T;

type Method = "handy.next" | "handy.previous" | "handy.check" | "handy.point";

export default function Session({ onStop }: { onStop: () => void }) {
  const room = useRoomContext();
  const { state: agentState, agent } = useVoiceAssistant();
  const { cameraTrack, localParticipant } = useLocalParticipant();
  const [guide, setGuide] = useState<GuideState>({ guide: null });
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [pointer, setPointer] = useState<PointerMsg | null>(null);
  const [recap, setRecap] = useState<Recap | null>(null);
  const [captions, setCaptions] = useState(true);
  const [busy, setBusy] = useState<Method | null>(null);

  // What we need to build a recap ourselves if the user ends early.
  const startedAt = useRef<number | null>(null);
  const mistakes = useRef<{ step: number; reason: string }[]>([]);
  const checks = useRef(0);

  useDataChannel("handy.state", (msg) => {
    const next = parse<GuideState>(msg.payload);
    setGuide((prev) => {
      if (next.guide && (!prev.guide || prev.guide.id !== next.guide.id)) {
        startedAt.current = Date.now();
        mistakes.current = [];
        checks.current = 0;
      }
      return next;
    });
    // Verdicts and boxes about an earlier step are stale once the step changes.
    const step = next.guide ? next.step.number : -1;
    setCheck((c) => (c && c.step === step ? c : null));
    setPointer((p) => (p && p.step === step ? p : null));
  });
  useDataChannel("handy.check", (msg) => {
    const result = parse<CheckResult>(msg.payload);
    checks.current += 1;
    if (result.verdict === "wrong") mistakes.current.push({ step: result.step, reason: result.reason });
    setCheck(result);
  });
  useDataChannel("handy.pointer", (msg) => setPointer(parse<PointerMsg>(msg.payload)));
  useDataChannel("handy.recap", (msg) => setRecap(parse<Recap>(msg.payload)));

  // Keep the phone screen awake while both hands are busy with screws.
  useEffect(() => {
    let lock: WakeLockSentinel | undefined;
    navigator.wakeLock?.request("screen").then((l) => (lock = l)).catch(() => {});
    return () => {
      lock?.release().catch(() => {});
    };
  }, []);

  async function press(method: Method) {
    if (!agent) return;
    setBusy(method);
    try {
      await room.localParticipant.performRpc({
        destinationIdentity: agent.identity,
        method,
        payload: "",
        responseTimeout: 20000,
      });
    } catch (e) {
      console.warn("rpc failed", e);
    } finally {
      setBusy(null);
    }
  }

  function end() {
    // Ending mid-repair still gets a summary of what happened so far.
    if (guide.guide && !recap && startedAt.current) {
      setRecap({
        guide_id: guide.guide.id,
        title: guide.guide.title,
        url: guide.guide.url,
        total_steps: guide.guide.total_steps,
        steps_completed: guide.completed.length,
        minutes: Math.round((Date.now() - startedAt.current) / 6000) / 10,
        checks: checks.current,
        mistakes_caught: mistakes.current,
      });
      return;
    }
    onStop();
  }

  const active = guide.guide !== null;

  return (
    <main className="session">
      <div className="camera-wrap">
        {cameraTrack ? (
          <VideoTrack
            trackRef={{ participant: localParticipant, publication: cameraTrack, source: Track.Source.Camera }}
            className="camera"
          />
        ) : (
          <div className="camera placeholder">Waiting for camera…</div>
        )}
        <PointerOverlay pointer={pointer} />
        <div className={`agent-pill state-${agentState}`}>
          <span className="dot" /> Handy is {agent ? agentState : "joining…"}
        </div>
        <button
          className={`cc ${captions ? "on" : ""}`}
          onClick={() => setCaptions((c) => !c)}
          aria-pressed={captions}
          aria-label="Captions"
        >
          CC
        </button>
        {check ? <VerdictBanner result={check} /> : captions && <Captions agentIdentity={agent?.identity} />}
      </div>

      {active ? (
        <div className="panel">
          {guide.step.number === 1 && <ToolsChecklist guide={guide.guide} />}
          <StepCard state={guide} />
        </div>
      ) : (
        <section className="step-card hint">
          <p>
            Say what you want to fix, for example <em>&quot;I want to replace the battery on my MacBook Air&quot;</em>.
          </p>
        </section>
      )}

      <nav className="controls">
        <TrackToggle source={Track.Source.Microphone} className="icon-btn" />
        {active && (
          <>
            <button className="secondary" disabled={!!busy} onClick={() => press("handy.previous")}>
              Back
            </button>
            <button className="secondary" disabled={!!busy} onClick={() => press("handy.point")}>
              {busy === "handy.point" ? "…" : "Where?"}
            </button>
            <button className="secondary" disabled={!!busy} onClick={() => press("handy.check")}>
              {busy === "handy.check" ? "…" : "Check"}
            </button>
            <button disabled={!!busy} onClick={() => press("handy.next")}>
              Next
            </button>
          </>
        )}
        <button className="danger" onClick={end}>
          End
        </button>
      </nav>

      {recap && (
        <RecapCard
          recap={recap}
          onClose={() => {
            setRecap(null);
            onStop();
          }}
        />
      )}
    </main>
  );
}
