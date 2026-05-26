"use client";

import React from "react";

// Lightweight markdown renderer for LLM answers — handles headings, bold,
// inline code, bullet lists, and fenced code blocks. Kept dependency-free on
// purpose so the bundle stays small and the build has nothing extra to resolve.

function renderInline(text: string, keyBase: string) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("`") && p.endsWith("`")) {
      return (
        <code key={`${keyBase}-${i}`} className="bg-zinc-900 text-amber-300 px-1 rounded text-xs">
          {p.slice(1, -1)}
        </code>
      );
    }
    if (p.startsWith("**") && p.endsWith("**")) {
      return (
        <strong key={`${keyBase}-${i}`} className="text-zinc-100 font-semibold">
          {p.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={`${keyBase}-${i}`}>{p}</React.Fragment>;
  });
}

export function Markdown({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  // Odd-indexed segments are inside ``` fences.
  const segments = text.split(/```/);

  segments.forEach((seg, si) => {
    if (si % 2 === 1) {
      const body = seg.replace(/^[a-zA-Z0-9]*\n/, ""); // drop the language hint line
      blocks.push(
        <pre key={`code-${si}`} className="bg-zinc-950 border border-zinc-800 rounded p-3 text-xs overflow-auto my-2">
          <code className="whitespace-pre">{body}</code>
        </pre>,
      );
      return;
    }

    let list: React.ReactNode[] = [];
    const flushList = (k: string) => {
      if (list.length) {
        blocks.push(<ul key={k} className="list-disc pl-5 space-y-1 my-1">{list}</ul>);
        list = [];
      }
    };

    seg.split("\n").forEach((ln, li) => {
      const key = `${si}-${li}`;
      const heading = ln.match(/^(#{1,3})\s+(.*)/);
      const bullet = ln.match(/^\s*[-*]\s+(.*)/);

      if (heading) {
        flushList(`ul-${key}`);
        const size = heading[1].length === 1 ? "text-lg" : heading[1].length === 2 ? "text-base" : "text-sm";
        blocks.push(
          <div key={key} className={`${size} font-semibold text-zinc-100 mt-3 mb-1`}>
            {renderInline(heading[2], key)}
          </div>,
        );
      } else if (bullet) {
        list.push(<li key={key}>{renderInline(bullet[1], key)}</li>);
      } else if (ln.trim() === "") {
        flushList(`ul-${key}`);
      } else {
        flushList(`ul-${key}`);
        blocks.push(<p key={key} className="leading-relaxed">{renderInline(ln, key)}</p>);
      }
    });

    flushList(`ul-end-${si}`);
  });

  return <div className="text-sm text-zinc-200 space-y-1">{blocks}</div>;
}
