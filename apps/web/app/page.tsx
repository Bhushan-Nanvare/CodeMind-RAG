"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import axios from "axios";
import { RepoInput } from "@/features/rag";
import { api } from "@/lib/api";
import { MAX_QUERY_LENGTH } from "@/lib/constants";
import type { CodeChunk } from "@/types";

export default function HomePage() {
  const [backendStatus, setBackendStatus] = useState<
    "connecting" | "online" | "offline"
  >("connecting");
  const [activeRepo, setActiveRepo] = useState<string | undefined>(undefined);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [sources, setSources] = useState<CodeChunk[]>([]);
  const [selectedSourceIdx, setSelectedSourceIdx] = useState<number>(0);
  const [meta, setMeta] = useState<{ ms: number; confidence: number } | null>(
    null,
  );
  const [err, setErr] = useState<string | null>(null);

  // Free-tier hosts (Render) sleep when idle, so the first request can take
  // 30–60s to cold-start. Poll until it answers instead of failing on attempt 1.
  useEffect(() => {
    let cancelled = false;
    const url = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

    const ping = async () => {
      try {
        const res = await fetch(`${url}/api/health`, {
          signal: AbortSignal.timeout(5000),
        });
        return res.ok;
      } catch {
        return false;
      }
    };

    (async () => {
      for (let attempt = 0; !cancelled; attempt++) {
        if (await ping()) {
          if (!cancelled) setBackendStatus("online");
          return;
        }
        // Stay in "connecting" through the cold-start window (~60s),
        // then soften to "offline" but keep retrying in the background.
        if (!cancelled) setBackendStatus(attempt >= 12 ? "offline" : "connecting");
        await new Promise((r) => setTimeout(r, 5000));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const statusColor = {
    connecting: "#f59e0b",
    online: "#10b981",
    offline: "#64748b",
  }[backendStatus];

  const statusLabel = {
    connecting: "Connecting to backend…",
    online: "Backend online",
    offline: "Backend waking up — retrying…",
  }[backendStatus];

  const disabledAsk = backendStatus !== "online" || !activeRepo?.trim();

  const onAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    const rn = activeRepo?.trim();
    const q = question.trim();
    if (!rn || !q) return;
    setLoading(true);
    setErr(null);
    setAnswer(null);
    setSources([]);
    setSelectedSourceIdx(0);
    setMeta(null);
    try {
      const res = await api.query({
        question: q,
        repo_name: rn,
        top_k: 10,
      });
      setAnswer(res.answer);
      setSources(res.sources || []);
      setSelectedSourceIdx(0);
      setMeta({ ms: res.query_time_ms, confidence: res.confidence_score });
    } catch (e: unknown) {
      let msg = "Query failed";
      if (axios.isAxiosError(e)) {
        const d = e.response?.data as { detail?: string } | undefined;
        msg = d?.detail || e.message || msg;
      } else if (e instanceof Error) {
        msg = e.message;
      }
      setErr(msg);
    } finally {
      setLoading(false);
    }
  };

  const selected = sources[selectedSourceIdx];

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "#0f1117",
        padding: "1.25rem",
      }}
    >
      <div style={{ maxWidth: "1400px", margin: "0 auto" }}>
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1rem",
            marginBottom: "1rem",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
              <div style={{ fontSize: "1.25rem", fontWeight: 800, color: "#e2e8f0" }}>
                CodeMind
              </div>
              <div
                style={{
                  fontSize: "1.25rem",
                  fontWeight: 800,
                  background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                RAG
              </div>
              <div style={{ color: "#64748b", fontSize: "0.85rem" }}>
                IDE-style workspace
              </div>
            </div>
            <div style={{ color: "#64748b", fontSize: "0.85rem" }}>
              Index a repo → ask questions → verify citations.
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <Link
              href="/context-chat"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.5rem 0.9rem",
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                border: "1px solid #6366f1",
                borderRadius: "999px",
                fontSize: "0.8rem",
                fontWeight: 700,
                color: "#fff",
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              🧠 Full-Context Chat →
            </Link>

            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.5rem 0.75rem",
                background: "#1e2130",
                border: "1px solid #2d3448",
                borderRadius: "999px",
                fontSize: "0.8rem",
                color: "#e2e8f0",
                whiteSpace: "nowrap",
              }}
            >
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  background: statusColor,
                }}
              />
              {statusLabel}
            </div>
          </div>
        </header>

        {backendStatus !== "online" ? (
          <div
            style={{
              padding: "2.5rem 2rem",
              borderRadius: "0.75rem",
              border: "1px solid #2d3448",
              background: "#1e2130",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "1rem",
              textAlign: "center",
            }}
          >
            <div
              className="animate-spin"
              style={{
                width: "34px",
                height: "34px",
                border: "3px solid #2d3448",
                borderTopColor: "#8b5cf6",
                borderRadius: "50%",
              }}
            />
            <div style={{ color: "#e2e8f0", fontWeight: 700, fontSize: "1.05rem" }}>
              {backendStatus === "connecting"
                ? "Waking up the backend…"
                : "Still waking up — hang tight"}
            </div>
            <div
              style={{
                color: "#94a3b8",
                fontSize: "0.875rem",
                lineHeight: 1.6,
                maxWidth: "480px",
              }}
            >
              The API runs on a free tier that goes to sleep when idle, so the first
              request can take <strong style={{ color: "#cbd5e1" }}>30–60 seconds</strong>{" "}
              to spin back up. This page reconnects automatically — no action needed.
            </div>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "320px minmax(480px, 1fr) 360px",
              gap: "1rem",
              alignItems: "stretch",
            }}
          >
            {/* Left: repo panel */}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <div
                style={{
                  padding: "0.75rem 0.9rem",
                  background: "#111827",
                  border: "1px solid #2d3448",
                  borderRadius: "0.75rem",
                  color: "#e2e8f0",
                  fontSize: "0.85rem",
                  fontWeight: 700,
                }}
              >
                Repository
              </div>
              <RepoInput onIngestionComplete={(name) => setActiveRepo(name)} />
              <div
                style={{
                  padding: "0.75rem 0.9rem",
                  background: "#1e2130",
                  border: "1px solid #2d3448",
                  borderRadius: "0.75rem",
                  color: "#94a3b8",
                  fontSize: "0.8rem",
                  lineHeight: 1.4,
                }}
              >
                Active repo used for retrieval:
                <div
                  style={{
                    marginTop: "0.35rem",
                    color: activeRepo ? "#a5b4fc" : "#f59e0b",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={activeRepo}
                >
                  {activeRepo || "(none yet — ingest first)"}
                </div>
              </div>
            </div>

            {/* Middle: results + sources + preview */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                border: "1px solid #2d3448",
                borderRadius: "0.75rem",
                background: "#1e2130",
                overflow: "hidden",
                minHeight: "520px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "0.75rem 0.9rem",
                  background: "#111827",
                  borderBottom: "1px solid #2d3448",
                }}
              >
                <div style={{ color: "#e2e8f0", fontWeight: 700, fontSize: "0.85rem" }}>
                  Results
                </div>
                <div style={{ color: "#64748b", fontSize: "0.75rem" }}>
                  {meta ? `${meta.ms} ms · confidence ${meta.confidence.toFixed(2)}` : ""}
                </div>
              </div>

              <div
                style={{
                  padding: "0.9rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.9rem",
                }}
              >
                {err && (
                  <div style={{ fontSize: "0.85rem", color: "#f87171" }}>{err}</div>
                )}

                {answer ? (
                  <div
                    style={{
                      fontSize: "0.95rem",
                      color: "#e2e8f0",
                      lineHeight: 1.6,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {answer}
                  </div>
                ) : (
                  <div style={{ fontSize: "0.85rem", color: "#64748b" }}>
                    Ask a question on the right. Answers and citations will appear here.
                  </div>
                )}

                {sources.length > 0 && (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "minmax(240px, 340px) 1fr",
                      gap: "0.9rem",
                      alignItems: "start",
                    }}
                  >
                    <div
                      style={{
                        border: "1px solid #2d3448",
                        borderRadius: "0.75rem",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          padding: "0.6rem 0.75rem",
                          background: "#0f1117",
                          borderBottom: "1px solid #2d3448",
                          color: "#94a3b8",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                        }}
                      >
                        Sources ({sources.length})
                      </div>
                      <div style={{ maxHeight: "260px", overflow: "auto" }}>
                        {sources.map((s, i) => {
                          const active = i === selectedSourceIdx;
                          return (
                            <button
                              key={`${s.file_path}-${s.start_line}-${i}`}
                              onClick={() => setSelectedSourceIdx(i)}
                              type="button"
                              style={{
                                width: "100%",
                                textAlign: "left",
                                padding: "0.6rem 0.75rem",
                                background: active ? "#111827" : "transparent",
                                border: "none",
                                borderBottom: "1px solid #2d3448",
                                cursor: "pointer",
                              }}
                            >
                              <div
                                style={{
                                  fontSize: "0.75rem",
                                  color: "#a5b4fc",
                                  fontFamily:
                                    "ui-monospace, SFMono-Regular, Menlo, monospace",
                                }}
                              >
                                {s.file_path}
                              </div>
                              <div
                                style={{
                                  fontSize: "0.72rem",
                                  color: "#64748b",
                                  marginTop: "0.15rem",
                                }}
                              >
                                lines {s.start_line}–{s.end_line} · rrf{" "}
                                {s.rrf_score.toFixed(4)}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div
                      style={{
                        border: "1px solid #2d3448",
                        borderRadius: "0.75rem",
                        overflow: "hidden",
                        background: "#0f1117",
                      }}
                    >
                      <div
                        style={{
                          padding: "0.6rem 0.75rem",
                          borderBottom: "1px solid #2d3448",
                          color: "#94a3b8",
                          fontSize: "0.75rem",
                          fontWeight: 700,
                          display: "flex",
                          justifyContent: "space-between",
                          gap: "0.75rem",
                        }}
                      >
                        <div
                          style={{
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {selected
                            ? `${selected.file_path} (${selected.start_line}-${selected.end_line})`
                            : "Code preview"}
                        </div>
                      </div>
                      <pre
                        style={{
                          margin: 0,
                          padding: "0.75rem",
                          maxHeight: "260px",
                          overflow: "auto",
                          color: "#e2e8f0",
                          fontSize: "0.8rem",
                          lineHeight: 1.5,
                          fontFamily:
                            "ui-monospace, SFMono-Regular, Menlo, monospace",
                        }}
                      >
                        {selected?.snippet || ""}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right: prompt panel */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                border: "1px solid #2d3448",
                borderRadius: "0.75rem",
                background: "#1e2130",
                overflow: "hidden",
                minHeight: "520px",
              }}
            >
              <div
                style={{
                  padding: "0.75rem 0.9rem",
                  background: "#111827",
                  borderBottom: "1px solid #2d3448",
                  color: "#e2e8f0",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                }}
              >
                Prompt
              </div>
              <div
                style={{
                  padding: "0.9rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem",
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
                  {disabledAsk
                    ? "Ingest a repo first (left) to enable asking."
                    : "Ask a repo-specific question. The active repo is used for retrieval."}
                </div>

                <form
                  onSubmit={onAsk}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.6rem",
                  }}
                >
                  <textarea
                    value={question}
                    maxLength={MAX_QUERY_LENGTH}
                    onChange={(e) => setQuestion(e.target.value)}
                    disabled={disabledAsk || loading}
                    placeholder="e.g. Where is authentication enforced and which routes are protected?"
                    rows={10}
                    style={{
                      padding: "0.75rem",
                      borderRadius: "0.75rem",
                      border: "1px solid #2d3448",
                      background: "#0f1117",
                      color: "#e2e8f0",
                      fontSize: "0.9rem",
                      resize: "vertical",
                      lineHeight: 1.5,
                    }}
                  />
                  <button
                    type="submit"
                    disabled={disabledAsk || loading || !question.trim()}
                    style={{
                      padding: "0.6rem 0.9rem",
                      borderRadius: "0.75rem",
                      border: "none",
                      background: disabledAsk
                        ? "#334155"
                        : loading
                          ? "#475569"
                          : "#8b5cf6",
                      color: "#fff",
                      fontWeight: 700,
                      cursor: disabledAsk || loading ? "not-allowed" : "pointer",
                      fontSize: "0.9rem",
                    }}
                  >
                    {loading ? "Asking…" : "Ask"}
                  </button>
                </form>

                <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
                  Active repo:{" "}
                  <span style={{ color: activeRepo ? "#a5b4fc" : "#f59e0b" }}>
                    {activeRepo || "(none)"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
