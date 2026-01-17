import glob as globlib
import os
import re
import subprocess

from .constants import DIM, RESET


class ReadTool:
    name = "read"
    description = "Read file with line numbers (file path, not directory)"
    parameters = {"path": "string", "offset": "number?", "limit": "number?"}

    def run(self, args):
        lines = open(args["path"]).readlines()
        offset = args.get("offset", 0)
        limit = args.get("limit", len(lines))
        selected = lines[offset : offset + limit]
        return "".join(
            f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected)
        )


class WriteTool:
    name = "write"
    description = "Write content to file"
    parameters = {"path": "string", "content": "string"}

    def run(self, args):
        with open(args["path"], "w") as f:
            f.write(args["content"])
        return "ok"


class EditTool:
    name = "edit"
    description = "Replace old with new in file (old must be unique unless all=true)"
    parameters = {"path": "string", "old": "string", "new": "string", "all": "boolean?"}

    def run(self, args):
        text = open(args["path"]).read()
        old, new = args["old"], args["new"]
        if old not in text:
            return "error: old_string not found"
        count = text.count(old)
        if not args.get("all") and count > 1:
            return f"error: old_string appears {count} times, must be unique (use all=true)"
        replacement = (
            text.replace(old, new) if args.get("all") else text.replace(old, new, 1)
        )
        with open(args["path"], "w") as f:
            f.write(replacement)
        return "ok"


class GlobTool:
    name = "glob"
    description = "Find files by pattern, sorted by mtime"
    parameters = {"pat": "string", "path": "string?"}

    def run(self, args):
        pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
        files = globlib.glob(pattern, recursive=True)
        files = sorted(
            files,
            key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
            reverse=True,
        )
        return "\n".join(files) or "none"


class GrepTool:
    name = "grep"
    description = "Search files for regex pattern"
    parameters = {"pat": "string", "path": "string?"}

    def run(self, args):
        pattern = re.compile(args["pat"])
        hits = []
        for filepath in globlib.glob(args.get("path", ".") + "/**", recursive=True):
            try:
                for line_num, line in enumerate(open(filepath), 1):
                    if pattern.search(line):
                        hits.append(f"{filepath}:{line_num}:{line.rstrip()}")
            except Exception:
                pass
        return "\n".join(hits[:50]) or "none"


class BashTool:
    name = "bash"
    description = "Run shell command"
    parameters = {"cmd": "string"}
    confirm = True  # Safety flag

    def run(self, args):
        # Confirmation is now handled by the runner
        proc = subprocess.Popen(
            args["cmd"],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output_lines = []
        try:
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    print(f"  {DIM}│ {line.rstrip()}{RESET}", flush=True)
                    output_lines.append(line)
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            output_lines.append("\n(timed out after 30s)")
        return "".join(output_lines).strip() or "(empty)"


BUILTIN_TOOLS = [
    ReadTool(),
    WriteTool(),
    EditTool(),
    GlobTool(),
    GrepTool(),
    BashTool(),
]

TOOL_REGISTRY = {t.name: t for t in BUILTIN_TOOLS}
