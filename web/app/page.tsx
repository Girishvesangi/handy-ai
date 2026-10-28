"use client";

import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";
import Link from "next/link";
import { useState } from "react";
import Session from "./components/Session";

type Connection = { serverUrl: string; token: string };

export default function Home() {
  const [conn, setConn] = useState<Connection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [needsCode, setNeedsCode] = useState(false);
  const [code, setCode] = useState("");

  async function start() {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      if (data.needsCode) setNeedsCode(true);
      if (!res.ok) throw new Error(data.error ?? "Could not get a token");
      setConn(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  if (!conn) {
    return (
      <main className="landing">
        <h1>Handy</h1>
        <p className="tagline">A repair buddy that sees what you see.</p>
        <ol className="how">
          <li>Point your phone camera at your laptop.</li>
          <li>Say what you want to fix. Handy finds the iFixit guide.</li>
          <li>It talks you through each step and checks your work.</li>
        </ol>
        {needsCode && (
          <input
            className="code"
            type="password"
            placeholder="Access code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        )}
        <button onClick={start} disabled={loading}>
          {loading ? "Connecting…" : "Start a repair"}
        </button>
        {error && <p className="error">{error}</p>}
        <p className="safety">Always shut down and unplug a laptop before opening it.</p>
        <Link href="/evals" className="muted">
          How accurate is it? See the evals
        </Link>
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
      video={{ facingMode: "environment", resolution: { width: 1280, height: 720 } }}
      onDisconnected={() => setConn(null)}
      onError={(e) => setError(e.message)}
      className="room"
    >
      <Session onStop={() => setConn(null)} />
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}
