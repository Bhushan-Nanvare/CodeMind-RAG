/**
 * Cross-platform preinstall: remove npm/yarn lockfiles and require pnpm.
 * Replaces Unix-only `sh -c '...'` so `pnpm install` works on Windows.
 * Uses .cjs so this file is CommonJS even when a parent package has "type": "module".
 */
const fs = require("fs");
const path = require("path");

const root = process.cwd();
for (const name of ["package-lock.json", "yarn.lock"]) {
  const p = path.join(root, name);
  if (fs.existsSync(p)) {
    try {
      fs.unlinkSync(p);
    } catch {
      /* ignore */
    }
  }
}

const ua = process.env.npm_config_user_agent || "";
if (!ua.includes("pnpm")) {
  console.error(
    "This workspace must be installed with pnpm (not npm/yarn). Example: npm install -g pnpm && pnpm install",
  );
  process.exit(1);
}
