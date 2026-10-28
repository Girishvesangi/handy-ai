"use client";

import { useTranscriptions } from "@livekit/components-react";

/** The last thing said by each side, as live subtitles. */
export default function Captions({ agentIdentity }: { agentIdentity?: string }) {
  const lines = useTranscriptions();
  const agentLine = [...lines].reverse().find((l) => l.participantInfo.identity === agentIdentity);
  const userLine = [...lines].reverse().find((l) => l.participantInfo.identity !== agentIdentity);
  if (!agentLine && !userLine) return null;
  return (
    <div className="captions" aria-live="polite">
      {userLine && (
        <p className="you">
          <span>You</span> {userLine.text}
        </p>
      )}
      {agentLine && (
        <p>
          <span>Handy</span> {agentLine.text}
        </p>
      )}
    </div>
  );
}
