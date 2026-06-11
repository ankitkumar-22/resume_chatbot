"""
webrtc/signaling.py  —  Phase 4 placeholder

Design notes (to implement after v0.3-stable is committed):

POST /webrtc/offer
  - Accepts SDP offer from the browser RTCPeerConnection
  - aiortc produces the SDP answer
  - Returns answer to client

Audio track:
  - client getUserMedia → RTCPeerConnection → server (aiortc)
  - Server loops the audio track back to the client to prove the real-time pipe
  - VoicePanel shows a live audio-level meter

RTCDataChannel:
  - Wire existing /chat logic over a DataChannel so structured Q&A works over
    the same WebRTC connection

Lifecycle:
  - Handle iceconnectionstatechange on the client
  - Show connection status in VoicePanel
  - Auto-retry the offer on disconnect with exponential backoff

Dependencies to add when implementing:
  pip install aiortc aioice
"""
