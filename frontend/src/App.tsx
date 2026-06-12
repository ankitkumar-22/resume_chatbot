// src/App.tsx
import React, { useState, useRef, useEffect } from 'react';
import { api, Message, AssistantResponse } from './lib/api';
import './index.css';

const QUICK_PROMPTS = [
  "Summarize the candidate",
  "What are their top skills?",
  "How many years of experience?",
  "Are they a fit for a backend engineer role?",
  "What's missing from the resume?",
];

const SESSION_KEY = "resume_session_id";
const FILENAME_KEY = "resume_filename";

function mapHistory(msgs: any[]): Message[] {
  return msgs.map((msg, index) => {
    if (msg.role === "user") {
      return { id: `u-${index}`, role: "user" as const, text: msg.content };
    }
    return { id: `a-${index}`, role: "assistant" as const, data: msg.data as AssistantResponse };
  });
}

// ── Confidence badge ──────────────────────────────────────────────────────────
// Renders a small pill showing the numeric confidence value.
// Color shifts: green (≥0.8) → amber (≥0.5) → red (<0.5)
function ConfidencePill({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tier = value >= 0.8 ? "high" : value >= 0.5 ? "mid" : "low";
  return (
    <span className={`confidence confidence--${tier}`} title={`Confidence: ${pct}%`}>
      {pct}%
    </span>
  );
}

export default function App() {

  const [filename, setFilename] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [isReplacing, setIsReplacing] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isUploaded = !!sessionId;
  const viewState = sessionId !== null ? "chat" : "landing";

  // ── Restore session ──────────────────────────────────────────────────────
  useEffect(() => {
    const savedSessionId = localStorage.getItem(SESSION_KEY);
    const savedFilename  = localStorage.getItem(FILENAME_KEY);
    if (!savedSessionId) return;

    setFilename(savedFilename);
    setIsUploading(true);

    api.getHistory(savedSessionId)
      .then((history) => {
        setSessionId(savedSessionId);
        setMessages(mapHistory(history.messages));
      })
      .catch(() => {
        localStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(FILENAME_KEY);
        setFilename(null);
      })
      .finally(() => setIsUploading(false));
  }, []);

  // ── Auto-scroll ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  // ── Auto-resize textarea ─────────────────────────────────────────────────
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  // ── File upload ──────────────────────────────────────────────────────────
  const handleFileUpload = async (file: File) => {
    const okType = /\.(pdf|txt)$/i.test(file.name);
    if (!okType) return setErrorMsg("That file type won't work — upload a PDF or .txt.");
    if (file.size > 10 * 1024 * 1024) return setErrorMsg("That file is over 10 MB. Try a smaller one.");

    setErrorMsg(null);
    setIsUploading(true);
    if (isUploaded) setIsReplacing(true);

    try {
      const res = await api.uploadResume(file);
      const history = await api.getHistory(res.session_id);

      setSessionId(res.session_id);
      setFilename(file.name);
      setMessages(mapHistory(history.messages));

      localStorage.setItem(SESSION_KEY, res.session_id);
      localStorage.setItem(FILENAME_KEY, file.name);

      setTimeout(() => textareaRef.current?.focus(), 100);
    } catch (err) {
      setErrorMsg("Couldn't process that resume. Is the backend running?");
    } finally {
      setIsUploading(false);
      setIsReplacing(false);
      setIsDragActive(false);
    }
  };

  // ── Send message ─────────────────────────────────────────────────────────
  const handleSend = async (queryOverride?: string) => {
    const text = queryOverride || input.trim();
    if (!text || !sessionId || isSending) return;

    setInput("");
    setMessages(prev => [...prev, { id: Date.now().toString(), role: "user", text }]);
    setIsSending(true);
    setIsTyping(true);

    try {
      const data = await api.chat(sessionId, text);
      setMessages(prev => [...prev, { id: Date.now().toString(), role: "assistant", data }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: "error",
        text: "That didn't go through. Check the backend.",
      }]);
    } finally {
      setIsSending(false);
      setIsTyping(false);
    }
  };

  // ── Start over ───────────────────────────────────────────────────────────
  const handleStartOver = () => {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(FILENAME_KEY);
    setSessionId(null);
    setFilename(null);
    setMessages([]);
    setInput("");
    setErrorMsg(null);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files?.[0]) handleFileUpload(e.dataTransfer.files[0]);
  };

  const renderResumeChip = () => {
    if (isReplacing || (isUploading && isUploaded)) {
      return (
        <div className="resume-chip uploading">
          <div className="spin small"></div>
          <span className="fname">Uploading {filename || "resume"}…</span>
        </div>
      );
    }
    return (
      <div className="resume-chip">
        <span className="check">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        </span>
        <span className="fname">{filename}</span>
        <button className="replace" disabled={isUploading || isSending} onClick={() => fileInputRef.current?.click()}>
          Replace
        </button>
        <button className="replace start-over" disabled={isUploading || isSending} onClick={handleStartOver}>
          Start over
        </button>
      </div>
    );
  };

  return (
    <>
      <div className="topbar">
        <div className={`status ${isUploaded ? "live" : ""}`}>
          <span className="dot"></span>
          <span>{isUploaded ? "Connected" : "Waiting for file"}</span>
        </div>
      </div>

      <div className="app-shell">
        <div className="app" data-view={viewState}>
          <div className="stage">

            <div className="hero">
              <img className="logo" src="/logo.png" alt="Logo" />
              <h1>Hola!</h1>
            </div>

            {viewState === "landing" && !isUploading && (
              <p className="tagline">Upload a resume and I'll answer questions grounded in it.</p>
            )}

            <>
              <div id="uploadSlot">
                {!isUploaded ? (
                  <div
                    className={`dropzone ${isDragActive ? "drag" : ""} ${isUploading ? "busy" : ""}`}
                    onClick={() => !isUploading && fileInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setIsDragActive(true); }}
                    onDragLeave={() => setIsDragActive(false)}
                    onDrop={onDrop}
                  >
                    {isUploading ? (
                      <>
                        <div className="spin"></div>
                        <div className="dz-title" style={{ marginTop: 8 }}>
                          {filename ? `Reading ${filename}…` : "Restoring session…"}
                        </div>
                        <div className="dz-sub">Extracting and structuring the resume</div>
                      </>
                    ) : (
                      <>
                        <svg className="dz-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M12 16V4M12 4l-4 4M12 4l4 4" /><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
                        </svg>
                        <div className="dz-title">Upload your resume</div>
                        <div className="dz-sub">Drag and drop, or click to browse · PDF or TXT, up to 10 MB</div>
                        {errorMsg && <div className="dz-error">{errorMsg}</div>}
                      </>
                    )}
                  </div>
                ) : (
                  renderResumeChip()
                )}
              </div>
              <input
                type="file"
                ref={fileInputRef}
                accept=".pdf,.txt,application/pdf,text/plain"
                hidden
                onChange={(e) => {
                  if (e.target.files?.[0]) handleFileUpload(e.target.files[0]);
                  e.target.value = "";
                }}
              />
            </>

            {isUploaded && !isUploading && viewState === "landing" && (
              <p className="empty-hint">Resume loaded. Ask anything — each answer is labelled <em>Resume</em> or <em>Inference</em>.</p>
            )}

            <div className="thread" ref={threadRef}>
              {messages.map((m) => (
                <div key={m.id} className={`msg ${m.role}`}>
                  {m.role === "user" && (
                    <div className="bubble-user">{m.text}</div>
                  )}

                  {m.role === "assistant" && m.data && (
                    <div className="answer">
                      <p>{m.data.answer}</p>
                      <div className="meta">
                        <span className={`badge ${m.data.source}`}>
                          <span className="dot"></span>
                          {m.data.source === "resume" ? "Resume" : "Inference"}
                        </span>
                        <ConfidencePill value={m.data.confidence} />
                      </div>
                      {m.data.missing_data && m.data.missing_data.length > 0 && (
                        <div className="missing">
                          Not in resume:
                          {m.data.missing_data.map(md => (
                            <span key={md} className="tag">{md}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {m.role === "error" && (
                    <div className="errline"><span>{m.text}</span></div>
                  )}
                </div>
              ))}

              {isTyping && (
                <div className="msg assistant">
                  <div className="typing"><span></span><span></span><span></span></div>
                </div>
              )}
            </div>

            <div className={`composer ${!isUploaded || isUploading ? "locked" : ""}`}>
              <textarea
                ref={textareaRef}
                rows={1}
                placeholder={isUploaded ? "Ask about experience, skills, or fit…" : "Upload a resume to start chatting"}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                disabled={!isUploaded || isSending || isUploading}
              />
            </div>

            {isUploaded && (
              <div className="pills">
                {QUICK_PROMPTS.map(q => (
                  <button
                    key={q}
                    className="pill"
                    disabled={isSending || isUploading}
                    onClick={() => handleSend(q)}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14M13 6l6 6-6 6" />
                    </svg>
                    {q}
                  </button>
                ))}
              </div>
            )}

          </div>
        </div>
      </div>
    </>
  );
}