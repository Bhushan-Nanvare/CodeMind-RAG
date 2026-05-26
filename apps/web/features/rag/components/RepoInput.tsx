"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import type { IndexedRepo } from "@/types";

export interface RepoInputProps {
  onIngestionComplete?: (repoName: string) => void;
}

function githubRepoName(repoUrl: string): string {
  const cleaned = repoUrl.trim().replace(/\.git$/i, "");
  const m = cleaned.match(/github\.com\/([^/]+\/[^/]+)/i);
  return m ? m[1] : "";
}

export default function RepoInput({ onIngestionComplete }: RepoInputProps) {
  const [repoUrl, setRepoUrl] = useState("https://github.com/pypa/sampleproject");
  const [branch, setBranch] = useState("main");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [phase, setPhase] = useState<string>("");
  const [indexedRepos, setIndexedRepos] = useState<IndexedRepo[] | null>(null);

  const poll = useCallback(
    async (jobId: string, urlForName: string) => {
      const maxAttempts = 120;
      for (let i = 0; i < maxAttempts; i++) {
        const s = await api.getIngestionStatus(jobId);
        setProgress(s.progress_percent);
        setPhase(s.status);
        if (s.status === "completed") {
          // Prefer the backend's canonical repo_name after ingestion completes.
          // This prevents "active repo" mismatches when URL parsing differs.
          try {
            const list = await api.listRepos();
            setIndexedRepos(list.repos);
            const urlClean = urlForName.trim().replace(/\.git$/i, "");
            const match =
              list.repos.find((r) => r.repo_url === urlClean) ??
              list.repos.find((r) => r.repo_url.replace(/\/$/, "") === urlClean.replace(/\/$/, ""));
            onIngestionComplete?.(match?.repo_name || githubRepoName(urlForName));
          } catch {
            onIngestionComplete?.(githubRepoName(urlForName));
          }
          return;
        }
        if (s.status === "failed") {
          throw new Error(s.error || "Ingestion failed");
        }
        await new Promise((r) => setTimeout(r, 1500));
      }
      throw new Error("Timed out waiting for ingestion");
    },
    [onIngestionComplete],
  );

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    setProgress(0);
    setPhase("starting");
    try {
      const url = repoUrl.trim();
      const res = await api.ingestRepo({
        repo_url: url,
        branch: branch.trim() || "main",
      });
      await poll(res.job_id, url);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ingest failed";
      setError(msg);
    } finally {
      setBusy(false);
      setProgress(null);
      setPhase("");
    }
  };

  const derivedName = githubRepoName(repoUrl);

  return (
    <form
      onSubmit={onSubmit}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
        padding: "1rem",
        background: "#1e2130",
        border: "1px solid #2d3448",
        borderRadius: "0.75rem",
      }}
    >
      <div style={{ fontSize: "0.75rem", color: "#94a3b8", fontWeight: 600 }}>
        Index a GitHub repository
      </div>
      <div style={{ fontSize: "0.7rem", color: "#64748b" }}>
        Derived repo_name:{" "}
        <span style={{ color: derivedName ? "#a5b4fc" : "#f59e0b" }}>
          {derivedName || "(could not parse — expected https://github.com/owner/repo)"}
        </span>
      </div>
      <input
        type="url"
        value={repoUrl}
        onChange={(e) => setRepoUrl(e.target.value)}
        disabled={busy}
        placeholder="https://github.com/owner/repo"
        style={{
          padding: "0.5rem 0.75rem",
          borderRadius: "0.5rem",
          border: "1px solid #2d3448",
          background: "#0f1117",
          color: "#e2e8f0",
          fontSize: "0.875rem",
        }}
      />
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
        <label style={{ fontSize: "0.75rem", color: "#64748b" }}>Branch</label>
        <input
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          disabled={busy}
          style={{
            flex: 1,
            padding: "0.5rem 0.75rem",
            borderRadius: "0.5rem",
            border: "1px solid #2d3448",
            background: "#0f1117",
            color: "#e2e8f0",
            fontSize: "0.875rem",
          }}
        />
      </div>
      <button
        type="submit"
        disabled={busy}
        style={{
          padding: "0.5rem 1rem",
          borderRadius: "0.5rem",
          border: "none",
          background: busy ? "#475569" : "#6366f1",
          color: "#fff",
          fontWeight: 600,
          cursor: busy ? "not-allowed" : "pointer",
          fontSize: "0.875rem",
        }}
      >
        {busy ? "Indexing…" : "Start ingestion"}
      </button>
      {progress !== null && (
        <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
          Progress: {progress}% {phase ? `(${phase})` : ""}
        </div>
      )}
      {error && (
        <div style={{ fontSize: "0.75rem", color: "#f87171" }}>{error}</div>
      )}

      {indexedRepos && indexedRepos.length > 0 && (
        <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
          <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>
            Indexed repos (backend)
          </div>
          <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
            {indexedRepos.slice(0, 5).map((r) => (
              <li key={r.repo_name}>
                <code style={{ color: "#a5b4fc" }}>{r.repo_name}</code>{" "}
                <span style={{ color: "#64748b" }}>({r.chunk_count} chunks)</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}
