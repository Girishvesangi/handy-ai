// Hands the browser a short-lived ticket (JWT) to join a LiveKit room.
// The API secret stays on the server; the browser only ever sees the token.
import { AccessToken } from "livekit-server-sdk";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const { LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, ACCESS_CODE } = process.env;
  if (!LIVEKIT_URL || !LIVEKIT_API_KEY || !LIVEKIT_API_SECRET) {
    return NextResponse.json(
      { error: "LiveKit env vars are missing. See web/.env.example." },
      { status: 500 },
    );
  }

  const body = await req.json().catch(() => ({}));

  // Optional gate for public demos, so strangers can't run up your API bill.
  if (ACCESS_CODE) {
    if (body.code !== ACCESS_CODE) {
      return NextResponse.json({ error: "Access code required", needsCode: true }, { status: 401 });
    }
  }

  // A fresh room per session. The agent joins any new room automatically.
  const suffix = crypto.randomUUID().slice(0, 8);
  const roomName = `handy-${suffix}`;
  const identity = `user-${suffix}`;

  // The agent reads the preferred language from the participant's metadata.
  const language = typeof body.language === "string" ? body.language.slice(0, 40) : "";

  const at = new AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET, {
    identity,
    ttl: "15m",
    metadata: JSON.stringify({ language }),
  });
  at.addGrant({ roomJoin: true, room: roomName, canPublish: true, canSubscribe: true });

  return NextResponse.json({ serverUrl: LIVEKIT_URL, token: await at.toJwt() });
}
