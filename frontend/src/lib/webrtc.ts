// src/lib/webrtc.ts
//
// Self-contained WebRTC client for the audio loopback demo.
// Handles: getUserMedia → offer/answer signaling → ICE → loopback audio playback
//          → live audio level meter → exponential-backoff reconnection.

const API_BASE = "http://localhost:8000";
const ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }];
const MAX_RETRIES = 5;

// ── Types ─────────────────────────────────────────────────────────────────────

export type ConnectionStatus =
  | "idle"          // not started
  | "connecting"    // in flight (offer sent, waiting for ICE)
  | "connected"     // ICE completed — audio flowing
  | "disconnected"  // ICE dropped — retry scheduled
  | "failed";       // max retries exhausted or unrecoverable

export interface WebRTCCallbacks {
  onStatusChange: (status: ConnectionStatus) => void;
  onAudioLevel: (level: number) => void;  // 0–1, driven by AnalyserNode
}

// ── Client class ──────────────────────────────────────────────────────────────

export class WebRTCClient {
  private pc: RTCPeerConnection | null = null;
  private stream: MediaStream | null = null;
  private audioCtx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private animFrameId: number | null = null;
  private retryTimeout: ReturnType<typeof setTimeout> | null = null;
  private retryCount = 0;
  private stopped = false;
  private readonly cb: WebRTCCallbacks;

  constructor(callbacks: WebRTCCallbacks) {
    this.cb = callbacks;
  }

  // ── Public ─────────────────────────────────────────────────────────────────

  async start(): Promise<void> {
    this.stopped = false;
    this.retryCount = 0;
    await this._connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.retryTimeout) clearTimeout(this.retryTimeout);
    if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
    this._teardown(true);
    this.cb.onStatusChange("idle");
  }

  // ── Connection ─────────────────────────────────────────────────────────────

  private async _connect(): Promise<void> {
    if (this.stopped) return;
    this.cb.onStatusChange("connecting");

    try {
      // 1. Capture mic audio
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false,
      });

      // 2. Create RTCPeerConnection
      this.pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });

      // 3. Add local mic track to the connection
      this.stream.getAudioTracks().forEach((track) => {
        this.pc!.addTrack(track, this.stream!);
      });

      // 4. Handle incoming track (looped-back audio from server)
      this.pc.ontrack = (event) => {
        this._playAudio(event.streams[0]);
        this._setupMeter(event.streams[0]);
      };

      // 5. Watch ICE connection state — this is where reconnection lives
      this.pc.oniceconnectionstatechange = () => {
        const state = this.pc?.iceConnectionState;
        console.log("[WebRTC] ICE →", state);

        switch (state) {
          case "connected":
          case "completed":
            this.cb.onStatusChange("connected");
            this.retryCount = 0;   // clean slate on successful connect
            break;
          case "disconnected":
            this.cb.onStatusChange("disconnected");
            this._scheduleRetry();
            break;
          case "failed":
            this.cb.onStatusChange("failed");
            this._scheduleRetry();
            break;
          case "closed":
            if (!this.stopped) this.cb.onStatusChange("idle");
            break;
        }
      };

      // 6. Create offer and wait for full ICE gathering before sending
      const offer = await this.pc.createOffer();
      await this.pc.setLocalDescription(offer);
      await this._waitForIceGathering();

      // 7. Exchange SDP with the FastAPI signaling endpoint
      const res = await fetch(`${API_BASE}/webrtc/offer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sdp: this.pc.localDescription!.sdp,
          type: this.pc.localDescription!.type,
        }),
      });
      if (!res.ok) throw new Error(`Signaling HTTP ${res.status}`);

      const answer = await res.json();
      await this.pc.setRemoteDescription(new RTCSessionDescription(answer));

    } catch (err) {
      console.error("[WebRTC] connection error:", err);
      this.cb.onStatusChange("failed");
      this._scheduleRetry();
    }
  }

  // ── ICE gathering ──────────────────────────────────────────────────────────
  // Wait until all candidates are collected before shipping the offer.
  // The 4 s fallback ensures a partial-candidate offer still goes through.

  private _waitForIceGathering(): Promise<void> {
    return new Promise((resolve) => {
      if (!this.pc || this.pc.iceGatheringState === "complete") {
        resolve();
        return;
      }
      const onStateChange = () => {
        if (this.pc?.iceGatheringState === "complete") resolve();
      };
      this.pc.onicegatheringstatechange = onStateChange;
      setTimeout(resolve, 4_000);    // safety valve
    });
  }

  // ── Exponential backoff retry ──────────────────────────────────────────────
  // Delays: 1 s → 2 s → 4 s → 8 s → 16 s (capped), then gives up.

  private _scheduleRetry(): void {
    if (this.stopped || this.retryCount >= MAX_RETRIES) {
      this.cb.onStatusChange("failed");
      return;
    }
    const delay = Math.min(1_000 * 2 ** this.retryCount, 16_000);
    this.retryCount++;
    console.log(`[WebRTC] retry ${this.retryCount}/${MAX_RETRIES} in ${delay}ms`);
    this.retryTimeout = setTimeout(() => {
      this._teardown(false);   // keep the mic stream across retries
      this._connect();
    }, delay);
  }

  // ── Audio helpers ──────────────────────────────────────────────────────────

  private _playAudio(stream: MediaStream): void {
    // Create an off-DOM <audio> element — attaching to DOM isn't needed.
    const audio = document.createElement("audio");
    audio.srcObject = stream;
    audio.autoplay = true;
    audio.play().catch((e) => console.warn("[WebRTC] autoplay blocked:", e));
  }

  private _setupMeter(stream: MediaStream): void {
    this.audioCtx = new AudioContext();
    const src = this.audioCtx.createMediaStreamSource(stream);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 256;
    src.connect(this.analyser);
    this._pollLevel();
  }

  private _pollLevel(): void {
    if (!this.analyser) return;
    const buf = new Uint8Array(this.analyser.frequencyBinCount);
    const tick = () => {
      this.analyser!.getByteFrequencyData(buf);
      const avg = buf.reduce((sum, v) => sum + v, 0) / buf.length;
      this.cb.onAudioLevel(avg / 255);
      this.animFrameId = requestAnimationFrame(tick);
    };
    this.animFrameId = requestAnimationFrame(tick);
  }

  // ── Teardown ───────────────────────────────────────────────────────────────

  private _teardown(stopMic: boolean): void {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    this.audioCtx?.close();
    this.audioCtx = null;
    this.analyser = null;
    this.pc?.close();
    this.pc = null;
    if (stopMic && this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
  }
}