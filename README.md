# neumann (neu)

**The universal constructor for your terminal.**

An LLM-powered agentic coding assistant optimized for Qwen3-Coder-30B-A3B-Instruct. Chat with an AI that can read, write, and execute code in your workspace.

## Philosophy

**Opinionated defaults, hackable core.**

We have focused on a single API client (Oobabooga) and a single LLM (Qwen) because shipping something that works out of the box is better than endless configuration. Don't like our choices? **Fork it.** The entire codebase is designed to be hacked on.

Over time, we'll add better isolation to make it trivial to rip and replace individual pieces. But, already the code is simple and easy to hack on. Go wild.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/kajuberdut/neumann.git
cd neumann

# Install in editable mode (for hacking)
uv pip install -e .

# Run
./neu.py
```

## Configuration

Set these environment variables before running:

```bash
export API_URL="http://127.0.0.1:5000/v1/chat/completions"  # Oobabooga endpoint
```

Or configure directly in `neu.py` (lines 14-18).

## Usage

```bash
./neu.py                    # Start interactive session
./neu.py --tool-dir ./tools # Load additional tools from directory
./neu.py --system "..."     # Override system prompt
./neu.py --raw              # Show raw API responses for debugging
```

### Commands

- Type naturally to chat with the AI
- `/c` - Clear conversation history
- `/q` or `exit` - Quit

## How It Works

Neumann connects to an LLM API (Oobabooga) and enables it to manipulate your filesystem and run commands through **tool calling**. The LLM can autonomously chain multiple tool calls to accomplish complex tasks.

### Built-in Tools (for the LLM)

Six core tools are available to the AI:
- **read** - Read files with line numbers
- **write** - Write content to files
- **edit** - Replace text in files
- **glob** - Find files by pattern
- **grep** - Search files with regex
- **bash** - Run shell commands (requires confirmation)

### Tool Format

Neumann uses XML-based tool calling optimized for Qwen models:

```xml
<function=read>
<parameter=path>example.py</parameter>
</function>
```

The LLM generates these automatically - you just chat normally.

## Customization

### External Tools

Create custom tools by dropping Python files in a directory:

```python
# tools/my_tool.py
class MyTool:
    name = "my_tool"
    description = "Does something useful"
    parameters = {"arg": "string"}
    
    def run(self, args):
        return f"Result: {args['arg']}"
```

Then load them:

```bash
./neu.py --tool-dir ./tools
```

### Safety Confirmations

Tools marked with `confirm = True` require user approval before execution. By default, only `bash` requires confirmation.

## Architecture

- **SSE Streaming**: Real-time response streaming via Server-Sent Events
- **Agentic Loop**: Automatically executes tool calls until task completion

## License

See [LICENSE](LICENSE)
