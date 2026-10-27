"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useLocalParticipant,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { useState } from "react";

type Connection = { serverUrl: string; token: string };

export default function Home() {
  const [conn, setConn] = useState<Connection | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setError(null);
    const res = await fetch("/api/token", { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      setError(data.error ?? "Could not get a token");
      return;
    }
    setConn(data);
  }

  if (!conn) {
    return (
      <main className="center">
        <h1>Handy</h1>
        <p>Point your camera at a laptop and ask &quot;what is this?&quot;</p>
        <button onClick={start}>Start</button>
        {error && <p className="error">{error}</p>}
      </main>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={conn.serverUrl}
      token={conn.token}
      connect
      audio
      // "environment" asks phones for the back camera.
      video={{ facingMode: "environment" }}
      onDisconnected={() => setConn(null)}
      className="room"
    >
      <Session onStop={() => setConn(null)} />
      {/* Plays the agent's voice through your speaker. */}
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

function Session({ onStop }: { onStop: () => void }) {
  const { state } = useVoiceAssistant();
  const { cameraTrack, localParticipant } = useLocalParticipant();

  return (
    <main className="session">
      {cameraTrack ? (
        <VideoTrack
          trackRef={{
            participant: localParticipant,
            publication: cameraTrack,
            source: Track.Source.Camera,
          }}
          className="camera"
        />
      ) : (
        <div className="camera placeholder">Waiting for camera…</div>
      )}
      <div className="status">Handy is {state}</div>
      <button onClick={onStop}>Stop</button>
    </main>
  );
}
