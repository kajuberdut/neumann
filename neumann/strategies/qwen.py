import json
import os
import re

from .base import BaseStrategy


class QwenStrategy(BaseStrategy):
    """
    Strategy for Qwen/XML-style tool calling.
    """

    @property
    def name(self) -> str:
        return "qwen"

    def get_system_prompt(self, tool_registry: dict) -> str:
        prompt = f"Concise coding assistant. cwd: {os.getcwd()}\n\n"
        prompt += "You have access to the following tools:\n"

        for tool in tool_registry.values():
            param_str = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items())
            prompt += f"- {tool.name}({param_str}): {tool.description}\n"

        prompt += "\nTo use a tool, you MUST use this exact XML format:\n"
        prompt += "<function=tool_name>\n<parameter=param_name>value</parameter>\n</function>\n"
        prompt += "\nExample:\n<function=read>\n<parameter=path>file.txt</parameter>\n</function>\n"

        return prompt

    def parse_tool_calls(self, text: str) -> list[dict]:
        """Parses Qwen/XML-style tool calls from text content."""
        tools = []
        # Find all function blocks
        func_iter = re.finditer(r"<function=(\w+)>(.*?)</function>", text, re.DOTALL)
        for match in func_iter:
            name = match.group(1)
            body = match.group(2)
            args = {}
            # Parse parameters
            param_iter = re.finditer(
                r"<parameter=(\w+)>(.*?)</parameter>", body, re.DOTALL
            )
            for p_match in param_iter:
                key = p_match.group(1)
                # Use strip() to remove surrounding whitespace/newlines
                val = p_match.group(2).strip()
                args[key] = val

            tools.append(
                {
                    "id": f"call_{os.urandom(4).hex()}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args),
                    },
                }
            )
        return tools
