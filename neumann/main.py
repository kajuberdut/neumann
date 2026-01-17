"""
Neumann CLI
The universal constructor for your terminal.
"""

import importlib.util
import json
import os
import re
import urllib.request

from .cli import parse_args
from .constants import (
    BLUE,
    BOLD,
    CYAN,
    DEFAULT_API_URL,
    DIM,
    GREEN,
    RED,
    RESET,
)
from .sse_client import SSEClient
from .strategies import get_strategy
from .tools import TOOL_REGISTRY

API_URL = os.environ.get("NEU_API_URL", DEFAULT_API_URL)


def run_tool(name, args):
    try:
        tool = TOOL_REGISTRY.get(name)
        if not tool:
            return f"error: Tool '{name}' not found."

        # Check for confirmation requirement
        if getattr(tool, "confirm", False):
            print(f"\n{RED}⚠️  CAUTION: The model wants to execute '{name}':{RESET}")
            for k, v in args.items():
                val_str = str(v)
                # Truncate very long values (like file content) for display
                if len(val_str) > 200:
                    val_str = val_str[:200] + f"... ({len(val_str) - 200} more chars)"
                print(f"{RED}   {k}: {val_str}{RESET}")

            while True:
                choice = input(f"{BOLD}Allow execution? [y/N] {RESET}").lower().strip()
                if choice in ("y", "yes"):
                    break
                elif choice in ("n", "no", ""):
                    reason = input(
                        f"{DIM}Reason for rejection (optional): {RESET}"
                    ).strip()
                    msg = "User denied execution permission."
                    if reason:
                        msg += f" Reason: {reason}"
                    return f"error: {msg}"

        return tool.run(args)
    except Exception as err:
        return f"error: {err}"


def load_external_tools(tool_dir):
    """Loads custom tools from python files in the specified directory."""
    if not os.path.isdir(tool_dir):
        print(f"{RED}Warning: Tool directory '{tool_dir}' not found.{RESET}")
        return

    count = 0
    for filename in os.listdir(tool_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            filepath = os.path.join(tool_dir, filename)
            try:
                spec = importlib.util.spec_from_file_location(filename[:-3], filepath)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                tools_in_this_file = 0

                # Scan for tool classes
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # Must be a class defined in this file
                    if isinstance(attr, type) and attr.__module__ == module.__name__:
                        # Check contract
                        required = {"name", "description", "parameters", "run"}
                        missing = required - set(dir(attr))

                        if not missing:
                            try:
                                tool_instance = attr()
                                TOOL_REGISTRY[tool_instance.name] = tool_instance
                                count += 1
                                tools_in_this_file += 1
                            except Exception as e:
                                print(
                                    f"{RED}Failed to instantiate {attr_name} from {filename}: {e}{RESET}"
                                )

                        # Heuristic: If it has 'run' or 'parameters' but missed the check, warn the user
                        elif "run" in dir(attr) or "parameters" in dir(attr):
                            print(
                                f"{RED}Skipped potential tool '{attr_name}' in {filename}. Missing attributes: {missing}{RESET}"
                            )

                if tools_in_this_file == 0:
                    print(
                        f"{DIM}Loaded {filename} but found no valid tools (classes with name, description, parameters, run).{RESET}"
                    )

            except Exception as e:
                print(f"{RED}Error loading tool file {filename}: {e}{RESET}")

    if count > 0:
        # We print this to stderr so it doesn't interfere with the TUI if that evolves
        # but for now standard print is fine as it happens before main loop
        print(f"{GREEN}Loaded {count} external tools from {tool_dir}{RESET}")


def call_api(messages, stream=True):
    headers = {
        "Content-Type": "application/json",
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(
            {
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

    # Load external tools before starting
    if args.tool_dir:
        load_external_tools(args.tool_dir)

    messages = []

    # Use dynamic system prompt if not overridden
    strategy = get_strategy("qwen")
    system_prompt = (
        args.system if args.system else strategy.get_system_prompt(TOOL_REGISTRY)
    )

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
                    qwen_tools = strategy.parse_tool_calls(full_content)
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
