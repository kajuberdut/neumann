#!/usr/bin/env python3
# -------------------------------------------------------
#  N E U M A N N (neu)
#  [!] This file is the documentation.
#  [!] This file is the configuration.
#  [!] This file is the application.
#  The universal constructor for your terminal.
#  Optimized for Qwen3-Coder-30B-A3B-Instruct
# -------------------------------------------------------

import argparse
import glob as globlib
import json
import logging
import os
import re
import subprocess
import urllib.request

# Default local model is set to Qwen3 as this script is optimized for its XML tool calling
DEFAULT_LOCAL_MODEL = "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"

# API Configuration (Oobabooga)
API_URL = "http://127.0.0.1:5000/v1/chat/completions"
MODEL = os.environ.get("MODEL", DEFAULT_LOCAL_MODEL)

# ANSI colors
RESET, BOLD, DIM, ITALIC = "\033[0m", "\033[1m", "\033[2m", "\033[3m"
BLUE, CYAN, GREEN, YELLOW, RED = (
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
)

# -----------------------------------------------------------------------------
# VENDOR: sseclient-py
# Licensed under the Apache License, Version 2.0.
# https://github.com/mpetazzoni/sseclient
# -----------------------------------------------------------------------------

_FIELD_SEPARATOR = ":"


class SSEClient(object):
    """Implementation of a SSE client.
    See http://www.w3.org/TR/2009/WD-eventsource-20091029/ for the
    specification.
    """

    def __init__(self, event_source, char_enc="utf-8"):
        """Initialize the SSE client over an existing, ready to consume
        event source.
        """
        self._logger = logging.getLogger(self.__class__.__module__)
        self._logger.debug("Initialized SSE client from event source %s", event_source)
        self._event_source = event_source
        self._char_enc = char_enc

    def _read(self):
        """Read the incoming event source stream and yield event chunks."""
        data = b""
        for chunk in self._event_source:
            for line in chunk.splitlines(True):
                data += line
                if data.endswith((b"\r\r", b"\n\n", b"\r\n\r\n")):
                    yield data
                    data = b""
        if data:
            yield data

    def events(self):
        for chunk in self._read():
            event = Event()
            for line in chunk.splitlines():
                # Decode the line.
                line = line.decode(self._char_enc)

                # Lines starting with a separator are comments and are to be ignored.
                if not line.strip() or line.startswith(_FIELD_SEPARATOR):
                    continue

                data = line.split(_FIELD_SEPARATOR, 1)
                field = data[0]

                # Ignore unknown fields.
                if field not in event.__dict__:
                    self._logger.debug(
                        "Saw invalid field %s while parsing Server Side Event", field
                    )
                    continue

                if len(data) > 1:
                    if data[1].startswith(" "):
                        value = data[1][1:]
                    else:
                        value = data[1]
                else:
                    value = ""

                if field == "data":
                    event.__dict__[field] += value + "\n"
                else:
                    event.__dict__[field] = value

            # Events with no data are not dispatched.
            if not event.data:
                continue

            if event.data.endswith("\n"):
                event.data = event.data[0:-1]

            event.event = event.event or "message"
            yield event

    def close(self):
        """Manually close the event source stream."""
        self._event_source.close()


class Event(object):
    """Representation of an event from the event stream."""

    def __init__(self, id=None, event="message", data="", retry=None):
        self.id = id
        self.event = event
        self.data = data
        self.retry = retry

    def __str__(self):
        s = "{0} event".format(self.event)
        if self.id:
            s += " #{0}".format(self.id)
        if self.data:
            s += ", {0} byte{1}".format(len(self.data), "s" if len(self.data) else "")
        else:
            s += ", no data"
        if self.retry:
            s += ", retry in {0}ms".format(self.retry)
        return s


# -----------------------------------------------------------------------------
# END VENDOR
# -----------------------------------------------------------------------------


# --- Tool implementations ---


def tool_error_handler(func):
    """Decorator to catch exceptions in tools and return them as error strings."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return f"error: {e}"

    return wrapper


@tool_error_handler
def read(args):
    lines = open(args["path"]).readlines()
    offset = args.get("offset", 0)
    limit = args.get("limit", len(lines))
    selected = lines[offset : offset + limit]
    return "".join(f"{offset + idx + 1:4}| {line}" for idx, line in enumerate(selected))


@tool_error_handler
def write(args):
    with open(args["path"], "w") as f:
        f.write(args["content"])
    return "ok"


@tool_error_handler
def edit(args):
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


@tool_error_handler
def glob(args):
    pattern = (args.get("path", ".") + "/" + args["pat"]).replace("//", "/")
    files = globlib.glob(pattern, recursive=True)
    files = sorted(
        files,
        key=lambda f: os.path.getmtime(f) if os.path.isfile(f) else 0,
        reverse=True,
    )
    return "\n".join(files) or "none"


@tool_error_handler
def grep(args):
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


@tool_error_handler
def bash(args):
    print(f"\n{RED}⚠️  CAUTION: The model wants to run a shell command:{RESET}")
    print(f"{RED}   {args['cmd']}{RESET}")

    while True:
        choice = input(f"{BOLD}Allow execution? [y/N] {RESET}").lower().strip()
        if choice in ("y", "yes"):
            break
        elif choice in ("n", "no", ""):
            reason = input(f"{DIM}Reason for rejection (optional): {RESET}").strip()
            msg = "User denied execution permission."
            if reason:
                msg += f" Reason: {reason}"
            return f"error: {msg}"

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


# --- Tool definitions ---

TOOLS = {
    "read": (
        "Read file with line numbers (file path, not directory)",
        {"path": "string", "offset": "number?", "limit": "number?"},
        read,
    ),
    "write": (
        "Write content to file",
        {"path": "string", "content": "string"},
        write,
    ),
    "edit": (
        "Replace old with new in file (old must be unique unless all=true)",
        {"path": "string", "old": "string", "new": "string", "all": "boolean?"},
        edit,
    ),
    "glob": (
        "Find files by pattern, sorted by mtime",
        {"pat": "string", "path": "string?"},
        glob,
    ),
    "grep": (
        "Search files for regex pattern",
        {"pat": "string", "path": "string?"},
        grep,
    ),
    "bash": (
        "Run shell command",
        {"cmd": "string"},
        bash,
    ),
}


def run_tool(name, args):
    try:
        return TOOLS[name][2](args)
    except Exception as err:
        return f"error: {err}"


def parse_qwen_tools(text):
    """Parses Qwen/XML-style tool calls from text content.
    Example: <function=write><parameter=path>file.txt</parameter></function>
    """
    tools = []
    # Find all function blocks
    func_iter = re.finditer(r"<function=(\w+)>(.*?)</function>", text, re.DOTALL)
    for match in func_iter:
        name = match.group(1)
        body = match.group(2)
        args = {}
        # Parse parameters
        param_iter = re.finditer(r"<parameter=(\w+)>(.*?)</parameter>", body, re.DOTALL)
        for p_match in param_iter:
            key = p_match.group(1)
            # Use strip() to remove surrounding whitespace/newlines,
            # assuming params are either one-line or block content where trim is safe enough.
            val = p_match.group(2).strip()
            args[key] = val

        tools.append(
            {
                "id": f"call_{os.urandom(4).hex()}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(
                        args
                    ),  # Standard format expects stringified JSON
                },
            }
        )
    return tools


def get_system_prompt():
    """Generates the system prompt with explicit tool definitions."""
    prompt = f"Concise coding assistant. cwd: {os.getcwd()}\n\n"
    prompt += "You have access to the following tools:\n"

    for name, (desc, params, _) in TOOLS.items():
        param_str = ", ".join(f"{k}: {v}" for k, v in params.items())
        prompt += f"- {name}({param_str}): {desc}\n"

    prompt += "\nTo use a tool, you MUST use this exact XML format:\n"
    prompt += (
        "<function=tool_name>\n<parameter=param_name>value</parameter>\n</function>\n"
    )
    prompt += "\nExample:\n<function=read>\n<parameter=path>file.txt</parameter>\n</function>\n"

    return prompt


def call_api(messages, stream=True):
    headers = {
        "Content-Type": "application/json",
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            {
                "model": MODEL,
                "messages": messages,
                "stream": stream,
            }
        ).encode(),
        headers=headers,
    )
    try:
        response = urllib.request.urlopen(request)
        if stream:
            return SSEClient(response)
        return json.loads(response.read())
    except urllib.error.URLError as e:
        return {"error": str(e)}


def separator():
    return f"{DIM}{'─' * min(os.get_terminal_size().columns, 80)}{RESET}"


def render_markdown(text):
    if not text:
        return ""
    return re.sub(r"\*\*(.+?)\*\*", f"{BOLD}\\1{RESET}", text)


def clear_screen():
    print("\033c", end="")


def parse_args():
    parser = argparse.ArgumentParser(
        description="neumann (neu) - universal constructor for code"
    )
    parser.add_argument("--system", type=str, default=None, help="Custom system prompt")
    parser.add_argument(
        "--raw", action="store_true", help="Print raw API responses for debugging"
    )
    return parser.parse_args()


def print_history(messages):
    """Clears screen and reprints conversation history."""
    clear_screen()
    provider_name = "Local API"
    print(
        f"{BOLD}neumann{RESET} | {DIM}{provider_name} (Streaming){RESET} | {os.getcwd()}\n"
    )

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "user":
            if isinstance(content, str):  # Normal message
                print(separator())
                print(f"{BOLD}{BLUE}❯{RESET} {content}")
                print(separator())
            elif isinstance(content, list):  # Tool result
                for tool_res in content:
                    print(f"  {DIM}⎿  {tool_res['content'].splitlines()[0]}...{RESET}")

        elif role == "assistant":
            if content:
                print(f"\n{CYAN}⏺{RESET} {render_markdown(content)}")

            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    print(f"\n{GREEN}⏺ {tc['function']['name'].capitalize()}{RESET}")
    print()


def main():
    args = parse_args()
    messages = []

    # Use dynamic system prompt if not overridden
    system_prompt = args.system if args.system else get_system_prompt()

    print_history(messages)

    while True:
        try:
            user_input = input(f"{BOLD}{BLUE}❯{RESET} ").strip()

            if not user_input:
                continue

            if user_input in ("/q", "exit"):
                break

            if user_input == "/c":
                messages = []
                print_history(messages)
                continue

            print(separator())
            messages.append({"role": "user", "content": user_input})

            # agentic loop
            while True:
                payload_messages = [
                    {"role": "system", "content": system_prompt}
                ] + messages

                client_or_response = call_api(payload_messages, stream=True)

                if (
                    isinstance(client_or_response, dict)
                    and "error" in client_or_response
                ):
                    print(f"{RED}⏺ API Error: {client_or_response['error']}{RESET}")
                    break

                full_content = ""
                tool_calls_data = {}

                print(f"\n{CYAN}⏺{RESET} ", end="", flush=True)

                for event in client_or_response.events():
                    if event.data == "[DONE]":
                        break

                    if args.raw:
                        print(f"\n{DIM}[RAW] {event.data}{RESET}", end="")

                    try:
                        chunk_data = json.loads(event.data)
                        delta = chunk_data["choices"][0]["delta"]

                        # Handle Content
                        if "content" in delta and delta["content"]:
                            text_chunk = delta["content"]
                            full_content += text_chunk
                            print(render_markdown(text_chunk), end="", flush=True)

                        # Handle Tools (Standard - kept as fallback if model uses native despite no 'tools' prompt)
                        if "tool_calls" in delta and delta["tool_calls"]:
                            for tc in delta["tool_calls"]:
                                idx = tc.index
                                if idx not in tool_calls_data:
                                    tool_calls_data[idx] = {
                                        "id": "",
                                        "name": "",
                                        "args": "",
                                    }
                                if "id" in tc:
                                    tool_calls_data[idx]["id"] = tc["id"]
                                if "function" in tc:
                                    if "name" in tc["function"]:
                                        tool_calls_data[idx]["name"] = tc["function"][
                                            "name"
                                        ]
                                    if "arguments" in tc["function"]:
                                        tool_calls_data[idx]["args"] += tc["function"][
                                            "arguments"
                                        ]

                    except (json.JSONDecodeError, KeyError):
                        pass

                print()  # Newline after stream ends

                # Standard Tool Assembly
                tool_calls = []
                if tool_calls_data:
                    for idx in sorted(tool_calls_data.keys()):
                        data = tool_calls_data[idx]
                        tool_calls.append(
                            {
                                "id": data["id"] or f"call_{os.urandom(4).hex()}",
                                "type": "function",
                                "function": {
                                    "name": data["name"],
                                    "arguments": data["args"],
                                },
                            }
                        )

                # Qwen XML Tool Fallback (Primary method now)
                if not tool_calls and "<function=" in full_content:
                    qwen_tools = parse_qwen_tools(full_content)
                    if qwen_tools:
                        tool_calls.extend(qwen_tools)

                # Save full message
                assistant_msg = {"role": "assistant", "content": full_content}

                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls

                messages.append(assistant_msg)

                # Execute Tools
                if tool_calls:
                    for tc in tool_calls:
                        func_data = tc["function"]
                        tool_name = func_data["name"]
                        try:
                            tool_args = json.loads(func_data["arguments"])
                        except json.JSONDecodeError:
                            print(
                                f"{RED}⏺ Error parsing arguments for {tool_name}{RESET}"
                            )
                            tool_args = {}

                        arg_preview = (
                            str(list(tool_args.values())[0])[:50] if tool_args else ""
                        )
                        print(
                            f"\n{GREEN}⏺ {tool_name.capitalize()}{RESET}({DIM}{arg_preview}{RESET})"
                        )

                        result = run_tool(tool_name, tool_args)

                        result_lines = result.split("\n")
                        preview = result_lines[0][:60]
                        if len(result_lines) > 1:
                            preview += f" ... +{len(result_lines) - 1} lines"
                        elif len(result_lines[0]) > 60:
                            preview += "..."
                        print(f"  {DIM}⎿  {preview}{RESET}")

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "name": tool_name,
                                "content": result,
                            }
                        )
                else:
                    break  # End of agent loop

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as err:
            print(f"{RED}⏺ Error: {err}{RESET}")


if __name__ == "__main__":
    main()
