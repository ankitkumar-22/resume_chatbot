// src/components/VoicePanel.tsx
import React, { useState, useRef, useCallback } from "react";
import { WebRTCClient, ConnectionStatus } from "../lib/webrtc";

interface VoicePanelProps {
  disabled?: boolean;
}

// ── Copy + colour maps ────────────────────────────────────────────────────────

const STATUS_LABEL: Record<ConnectionStatus, string> = {
  idle:         "Voice off",
  connecting:   "Connecting…",
  connected:    "Live",
  disconnected: "Reconnecting…",
  failed:       "Failed — tap to retry",
};

// These reuse the CSS custom props already on .dot/.live in App's stylesheet;
// fallback hex values make VoicePanel render correctly even without them.
const STATUS_COLOR: Record<ConnectionStatus, string> = {
  idle:         "var(--clr-muted,  #6b7280)",
  connecting:   "var(--clr-warn,   #f59e0b)",
  connected:    "var(--clr-live,   #10b981)",
  disconnected: "var(--clr-warn,   #f59e0b)",
  failed:       "var(--clr-err,    #ef4444)",
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function VoicePanel({ disabled = false }: VoicePanelProps) {
  const [status, setStatus]   = useState<ConnectionStatus>("idle");
  const [level,  setLevel]    = useState(0);
  const clientRef             = useRef<WebRTCClient | null>(null);

  // "active" = session is up or being established (not idle / failed)
  const isActive =
    status === "connecting" ||
    status === "connected"  ||
    status === "disconnected";

  const handleToggle = useCallback(async () => {
    if (isActive) {
      clientRef.current?.stop();
      clientRef.current = null;
      setLevel(0);
    } else {
      // idle or failed → (re)start
      const client = new WebRTCClient({
        onStatusChange: setStatus,
        onAudioLevel:   setLevel,
      });
      clientRef.current = client;
      await client.start();
    }
  }, [isActive]);

  return (
    <div className="voice-panel">

      {/* ── Mic / stop toggle ─────────────────────────────────────────── */}
      <button
        className={`voice-btn${isActive ? " voice-btn--active" : ""}`}
        onClick={handleToggle}
        disabled={disabled}
        title={isActive ? "Stop voice" : "Start voice (audio loopback demo)"}
        aria-label={isActive ? "Stop voice" : "Start voice"}
      >
        {isActive ? <IconStop /> : <IconMic />}
      </button>

      {/* ── Status indicator ──────────────────────────────────────────── */}
      <div className="voice-status">
        <span
          className="voice-dot"
          style={{ backgroundColor: STATUS_COLOR[status] }}
        />
        <span className="voice-label">{STATUS_LABEL[status]}</span>
      </div>

      {/* ── Live audio level meter (only shown while session is active) ─ */}
      {isActive && (
        <div
          className="audio-meter"
          title={`Audio level: ${Math.round(level * 100)}%`}
          aria-label="Audio level meter"
        >
          <div
            className="audio-meter__fill"
            style={{ width: `${level * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function IconMic() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      width="18"
      height="18"
      aria-hidden="true"
    >
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8"  y1="23" x2="16" y2="23" />
    </svg>
  );
}

function IconStop() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      width="18"
      height="18"
      aria-hidden="true"
    >
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}