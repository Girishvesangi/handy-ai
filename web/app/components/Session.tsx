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
import { useEffect, useState } from "react";
import type { CheckResult, GuideState } from "../lib/types";
import StepCard from "./StepCard";
import VerdictBanner from "./VerdictBanner";

const decoder = new TextDecoder();

export default function Session({ onStop }: { onStop: () => void }) {
  const room = useRoomContext();
  const { state: agentState, agent } = useVoiceAssistant();
  const { cameraTrack, localParticipant } = useLocalParticipant();
  const [guide, setGuide] = useState<GuideState>({ guide: null });
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [busy, setBusy] = useState(false);

  useDataChannel("handy.state", (msg) => {
    const next = JSON.parse(decoder.decode(msg.payload)) as GuideState;
    setGuide(next);
    // A verdict about an earlier step is stale once the step changes.
    setCheck((c) => (c && next.guide && c.step === next.step.number ? c : null));
  });
  useDataChannel("handy.check", (msg) => {
    setCheck(JSON.parse(decoder.decode(msg.payload)) as CheckResult);
  });

  // Keep the phone screen awake while both hands are busy with screws.
  useEffect(() => {
    let lock: WakeLockSentinel | undefined;
    navigator.wakeLock?.request("screen").then((l) => (lock = l)).catch(() => {});
    return () => {
      lock?.release().catch(() => {});
    };
  }, []);

  async function press(method: "handy.next" | "handy.previous" | "handy.check") {
    if (!agent) return;
    setBusy(true);
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
      setBusy(false);
    }
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
        <div className={`agent-pill state-${agentState}`}>
          <span className="dot" /> Handy is {agent ? agentState : "joining…"}
        </div>
        {check && <VerdictBanner result={check} />}
      </div>

      {active ? (
        <StepCard state={guide} />
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
            <button className="secondary" disabled={busy} onClick={() => press("handy.previous")}>
              Back
            </button>
            <button className="secondary" disabled={busy} onClick={() => press("handy.check")}>
              Check
            </button>
            <button disabled={busy} onClick={() => press("handy.next")}>
              Next
            </button>
          </>
        )}
        <button className="danger" onClick={onStop}>
          End
        </button>
      </nav>
    </main>
  );
}
