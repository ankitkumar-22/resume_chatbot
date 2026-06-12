"""
webrtc/signaling.py  —  Phase 4: audio loopback over aiortc

POST /webrtc/offer
    Accepts an SDP offer from the browser RTCPeerConnection.
    Registers an audio loopback track, then exchanges SDP.
    Returns the SDP answer.

GET /webrtc/status
    Returns the count of live peer connections (debug / healthcheck).

Design note:
    The @pc.on("track") handler MUST be registered before setRemoteDescription
    so it fires during SDP parsing. That way the loopback track is already
    added to the connection when createAnswer() builds the SDP answer —
    so the browser receives recvonly audio in the same negotiation round.
"""

import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

router = APIRouter(prefix="/webrtc", tags=["webrtc"])

# ── Module-level state ─────────────────────────────────────────────────────────

# All live peer connections — iterated on shutdown for clean teardown.
_pcs: set[RTCPeerConnection] = set()

# MediaRelay fans incoming frames out to one or more subscribers without
# copying audio buffers; mandatory for correct aiortc loopback.
_relay = MediaRelay()


# ── Schemas ────────────────────────────────────────────────────────────────────

class SdpOffer(BaseModel):
    sdp: str
    type: str   # always "offer" from the browser


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/status")
async def webrtc_status():
    """Debug endpoint — returns number of active peer connections."""
    return {"active_connections": len(_pcs)}


@router.post("/offer")
async def webrtc_offer(offer: SdpOffer):
    """
    Full signaling round-trip:
      browser SDP offer → aiortc answer + loopback track → browser
    """
    pc = RTCPeerConnection()
    _pcs.add(pc)

    # ── Lifecycle ──────────────────────────────────────────────────────────────
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        state = pc.connectionState
        print(f"[WebRTC] peer {id(pc):#x} → {state}")
        if state in ("failed", "closed"):
            await pc.close()
            _pcs.discard(pc)

    # ── Audio loopback ─────────────────────────────────────────────────────────
    # Registered BEFORE setRemoteDescription so it's called during SDP parsing.
    @pc.on("track")
    def on_track(track):
        print(f"[WebRTC] track received  kind={track.kind}")
        if track.kind == "audio":
            # relay.subscribe() wraps the remote track in a frame-pumped
            # LocalAudioTrack that aiortc can transmit back to the browser.
            pc.addTrack(_relay.subscribe(track))

    # ── SDP exchange ───────────────────────────────────────────────────────────
    await pc.setRemoteDescription(
        RTCSessionDescription(sdp=offer.sdp, type=offer.type)
    )
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }


# ── Shutdown helper ────────────────────────────────────────────────────────────

async def close_all() -> None:
    """
    Close every open RTCPeerConnection.
    Call from FastAPI's shutdown event so aiortc threads exit cleanly.
    """
    coros = [pc.close() for pc in list(_pcs)]
    _pcs.clear()
    if coros:
        await asyncio.gather(*coros, return_exceptions=True)
    print("[WebRTC] all connections closed.")