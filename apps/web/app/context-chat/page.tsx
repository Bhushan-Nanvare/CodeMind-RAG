"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Markdown } from "@/components/Markdown";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface SessionMeta {
  repo_name: string;
  total_files_packed: number;
  total_tokens_sent: number;
  truncated: boolean;
  dropped_files: number;
  cache_hit: boolean;
}

export default function ContextChatPage() {
  const [repoUrl, setRepoUrl] = useState("");
  const [branch, setBranch] = useState("main");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [meta, setMeta] = useState<SessionMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [err, setErr] = useState("");
  const [repoLocked, setRepoLocked] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function loadRepo() {
    if (!repoUrl.trim()) return;
    setIndexing(true);
    setErr("");
    setMessages([]);
    setMeta(null);
    try {
      // Prime the cache with a simple "summarize" question
      const r = await api.contextChat(
        repoUrl,
        "In one sentence, what does this repository do?",
        branch,
      );
      setMeta({
        repo_name: r.repo_name,
        total_files_packed: r.total_files_packed,
        total_tokens_sent: r.total_tokens_sent,
        truncated: r.truncated,
        dropped_files: r.dropped_files,
        cache_hit: r.cache_hit,
      });
      setMessages([
        { role: "assistant", content: `**Repository loaded:** \`${r.repo_name}\`\n\n${r.answer}` },
      ]);
      setRepoLocked(true);
    } catch (e: any) {
      setErr(e.response?.data?.detail ?? e.message);
    } finally {
      setIndexing(false);
    }
  }

  async function ask() {
    if (!question.trim() || loading) return;
    const q = question.trim();
    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);
    setErr("");

    try {
      const r = await api.contextChat(repoUrl, q, branch);
      setMessages((prev) => [...prev, { role: "assistant", content: r.answer }]);
      // Update meta with latest (cache_hit will be true after first load)
      setMeta((prev) => prev ? { ...prev, cache_hit: r.cache_hit } : prev);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (e: any) {
      setErr(e.response?.data?.detail ?? e.message);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `_Error: ${e.response?.data?.detail ?? e.message}_` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setRepoUrl("");
    setBranch("main");
    setMessages([]);
    setMeta(null);
    setRepoLocked(false);
    setErr("");
  }

  return (
    <div className="flex flex-col h-screen max-h-screen">
      {/* Header */}
      <div className="shrink-0 border-b border-zinc-800 bg-zinc-950 px-6 py-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <Link
              href="/"
              className="text-xs text-indigo-400 hover:text-indigo-300 inline-block mb-1"
            >
              ← Back to Q&A Search
            </Link>
            <h1 className="text-lg font-semibold">🧠 Full Context Chat</h1>
            <p className="text-xs text-zinc-500 mt-0.5">
              Packs the entire repo into context — best for architecture and cross-cutting questions
            </p>
          </div>
          {repoLocked && (
            <button
              onClick={reset}
              className="text-xs px-3 py-1.5 rounded border border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-500"
            >
              Change repo
            </button>
          )}
        </div>

        {/* Repo input — locked after loading */}
        {!repoLocked ? (
          <div className="flex gap-2">
            <input
              className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadRepo()}
              disabled={indexing}
            />
            <input
              className="w-24 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              placeholder="main"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              disabled={indexing}
            />
            <button
              onClick={loadRepo}
              disabled={indexing || !repoUrl.trim()}
              className="px-4 py-2 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm whitespace-nowrap"
            >
              {indexing ? "Loading repo..." : "Load Repo"}
            </button>
          </div>
        ) : (
          /* Stats bar when repo is loaded */
          meta && (
            <div className="flex gap-5 text-xs text-zinc-500">
              <span>
                repo: <code className="text-indigo-400">{meta.repo_name}</code>
              </span>
              <span>
                files packed: <span className="text-zinc-300">{meta.total_files_packed}</span>
              </span>
              <span>
                tokens: <span className="text-zinc-300">{meta.total_tokens_sent.toLocaleString()}</span>
              </span>
              {meta.truncated && (
                <span className="text-yellow-500">
                  ⚠ {meta.dropped_files} files dropped (token limit)
                </span>
              )}
              {meta.cache_hit && (
                <span className="text-green-600">⚡ cached</span>
              )}
            </div>
          )
        )}

        {err && <div className="mt-2 text-red-400 text-xs">{err}</div>}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && !indexing && (
          <div className="text-zinc-600 text-sm mt-8 text-center">
            {repoLocked
              ? "Ask anything about the codebase above."
              : "Load a GitHub repo to start chatting with its full source code."}
          </div>
        )}

        {indexing && (
          <div className="flex items-center gap-3 text-zinc-500 text-sm mt-8">
            <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
            Cloning and packing repository... this may take 30–60 seconds.
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-3xl rounded-lg px-4 py-3 text-sm ${
                m.role === "user"
                  ? "bg-indigo-900 border border-indigo-700 text-zinc-100"
                  : "bg-zinc-900 border border-zinc-800 text-zinc-200"
              }`}
            >
              <Markdown text={m.content} />
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3">
              <div className="flex gap-1 items-center">
                <div className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-1.5 h-1.5 bg-zinc-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      {repoLocked && (
        <div className="shrink-0 border-t border-zinc-800 bg-zinc-950 px-6 py-4">
          <div className="flex gap-2">
            <input
              className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              placeholder="Ask anything about the codebase..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && ask()}
              disabled={loading}
            />
            <button
              onClick={ask}
              disabled={loading || !question.trim()}
              className="px-4 py-2.5 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-sm"
            >
              Ask
            </button>
          </div>
          <div className="text-xs text-zinc-700 mt-1.5">
            Enter to send · Full context mode · {meta?.total_tokens_sent.toLocaleString()} tokens in context
          </div>
        </div>
      )}
    </div>
  );
}
