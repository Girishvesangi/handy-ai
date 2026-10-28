"""Keeps the most recent camera frame from the user, ready to send to the checker."""

from __future__ import annotations

import asyncio
import logging

from livekit import rtc
from livekit.agents.utils import images

logger = logging.getLogger("handy.frames")

ENCODE = images.EncodeOptions(
    format="JPEG",
    quality=85,
    resize_options=images.ResizeOptions(width=1024, height=1024, strategy="scale_aspect_fit"),
)


class LatestFrame:
    """Subscribes to the user's camera track and remembers only the newest frame."""

    def __init__(self, room: rtc.Room) -> None:
        self._room = room
        self._frame: rtc.VideoFrame | None = None
        self._task: asyncio.Task | None = None
        room.on("track_subscribed", self._on_track)
        for p in room.remote_participants.values():
            for pub in p.track_publications.values():
                if pub.track and pub.kind == rtc.TrackKind.KIND_VIDEO:
                    self._on_track(pub.track, pub, p)

    def _on_track(self, track: rtc.Track, pub: rtc.RemoteTrackPublication, participant) -> None:
        if track.kind != rtc.TrackKind.KIND_VIDEO:
            return
        if self._task:
            self._task.cancel()
        self._task = asyncio.create_task(self._read(rtc.VideoStream(track)))
        logger.info("watching camera from %s", participant.identity)

    async def _read(self, stream: rtc.VideoStream) -> None:
        async for event in stream:
            self._frame = event.frame

    def jpeg(self) -> bytes | None:
        """The newest frame as JPEG, or None if the camera hasn't sent anything yet."""
        if self._frame is None:
            return None
        return images.encode(self._frame, ENCODE)

    async def aclose(self) -> None:
        if self._task:
            self._task.cancel()
