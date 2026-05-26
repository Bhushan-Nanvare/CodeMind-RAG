export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export const API_TIMEOUT =
  Number(process.env.NEXT_PUBLIC_API_TIMEOUT) || 30000;

export const MAX_QUERY_LENGTH =
  Number(process.env.NEXT_PUBLIC_MAX_QUERY_LENGTH) || 500;

export const SUPPORTED_LANGUAGES = [
  "python",
  "javascript",
  "typescript",
  "java",
] as const;

export const EXCLUDED_DIRS = [
  "node_modules",
  ".git",
  "__pycache__",
  "dist",
  "build",
  "venv",
  ".venv",
  "vendor",
  ".next",
  ".nuxt",
];

export const SUPPORTED_EXTENSIONS = [
  ".py",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".java",
];
