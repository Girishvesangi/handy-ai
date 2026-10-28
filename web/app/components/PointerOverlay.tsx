"use client";

import { useEffect, useRef, useState } from "react";
import type { PointerMsg } from "../lib/types";

// How long a box stays on screen; the camera moves, so old boxes drift off target.
const SHOW_MS = 8000;

/**
 * Draws the agent's box on top of the camera view. The video uses
 * object-fit: cover, so part of the frame is cropped; we redo that crop math
 * to land the box on the right pixels.
 */
export default function PointerOverlay({ pointer }: { pointer: PointerMsg | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!pointer?.found) return;
    setVisible(true);
    const t = setTimeout(() => setVisible(false), SHOW_MS);
    return () => clearTimeout(t);
  }, [pointer]);

  let rect: { left: number; top: number; width: number; height: number } | null = null;
  if (pointer?.found && pointer.box.length === 4 && size.w > 0) {
    // Fall back to the on-screen video's own size if the agent didn't send one.
    const video = ref.current?.parentElement?.querySelector("video");
    const fw = pointer.frame_w || video?.videoWidth || size.w;
    const fh = pointer.frame_h || video?.videoHeight || size.h;
    const scale = Math.max(size.w / fw, size.h / fh);
    const dw = fw * scale;
    const dh = fh * scale;
    const ox = (size.w - dw) / 2;
    const oy = (size.h - dh) / 2;
    const [ymin, xmin, ymax, xmax] = pointer.box;
    rect = { left: ox + xmin * dw, top: oy + ymin * dh, width: (xmax - xmin) * dw, height: (ymax - ymin) * dh };
  }

  return (
    <div ref={ref} className="pointer-layer" aria-hidden={!visible}>
      {rect && pointer && (
        <div className={`pointer-box ${visible ? "on" : ""}`} style={rect}>
          <span className="pointer-label">{pointer.label}</span>
        </div>
      )}
    </div>
  );
}
