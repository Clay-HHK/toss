#!/usr/bin/env node

/**
 * Toss CLI - thin npm wrapper.
 *
 * Ensures `uv` is available, then delegates to the Python CLI via `uvx`.
 * This lets users run `npx toss-cli join server/CODE` with zero Python setup.
 */

const { execSync, execFileSync, spawnSync } = require("child_process");
const os = require("os");

const REPO = "https://github.com/Clay-HHK/toss.git";
const TOOL_SPEC = `toss @ git+${REPO}`;

function which(cmd) {
  try {
    const out = execSync(
      os.platform() === "win32" ? `where ${cmd}` : `command -v ${cmd}`,
      { stdio: ["pipe", "pipe", "pipe"], encoding: "utf-8" }
    );
    return out.trim().split("\n")[0];
  } catch {
    return null;
  }
}

function installUv() {
  console.error("uv not found. Installing...");
  if (os.platform() === "win32") {
    spawnSync(
      "powershell",
      ["-c", "irm https://astral.sh/uv/install.ps1 | iex"],
      { stdio: "inherit" }
    );
  } else {
    spawnSync("sh", ["-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"], {
      stdio: "inherit",
    });
  }

  // After install, uv is typically in ~/.local/bin or ~/.cargo/bin
  const home = os.homedir();
  const candidates = [
    `${home}/.local/bin/uv`,
    `${home}/.cargo/bin/uv`,
  ];
  for (const p of candidates) {
    try {
      execFileSync(p, ["--version"], { stdio: "pipe" });
      return p;
    } catch {
      // not here
    }
  }

  // Try PATH again (installer may have updated it)
  const found = which("uv");
  if (found) return found;

  console.error(
    "Failed to locate uv after install. Please install manually:\n" +
    "  https://docs.astral.sh/uv/getting-started/installation/"
  );
  process.exit(1);
}

function main() {
  let uv = which("uv");
  if (!uv) {
    uv = installUv();
  }

  const args = process.argv.slice(2);
  const result = spawnSync(uv, ["tool", "run", "--from", TOOL_SPEC, "toss", ...args], {
    stdio: "inherit",
    env: { ...process.env },
  });

  process.exit(result.status ?? 1);
}

main();
