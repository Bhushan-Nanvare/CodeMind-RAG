import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodeMind RAG — Intelligent Codebase Search",
  description:
    "Ask natural language questions about your codebase and get instant, cited answers.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
