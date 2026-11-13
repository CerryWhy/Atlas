// Esegue un comando dall'ambiente virtuale Python del repo (.venv), su Windows e POSIX.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const binDir = process.platform === "win32" ? join(root, ".venv", "Scripts") : join(root, ".venv", "bin");
if (!existsSync(binDir)) {
  console.error("Manca .venv: vedi README (python -m venv .venv && pip install -e .[dev])");
  process.exit(1);
}
const [cmd, ...args] = process.argv.slice(2);
const exe = join(binDir, process.platform === "win32" ? `${cmd}.exe` : cmd);
const env = { ...process.env, PYTHONUTF8: "1" }; // console Windows: niente cp1252
const child = spawn(existsSync(exe) ? exe : cmd, args, { cwd: root, stdio: "inherit", env });
child.on("exit", (code) => process.exit(code ?? 1));
