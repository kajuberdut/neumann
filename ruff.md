Here is a quick reference guide for managing Python code with Ruff and uv.

### 1. Install Ruff

Use `uv` to install Ruff globally as a tool.

```bash
uv tool install ruff

```

### 2. Format All Files

This reformats your code (similar to Black) to meet standard style guidelines. The `.` targets the current directory.

```bash
ruff format .

```

### 3. Auto-fix Issues

This runs the linter and automatically corrects simple errors (like removing unused variables or adding missing whitespace).

```bash
ruff check --fix .

```

### 4. Sort & Organize Imports

In Ruff, import sorting is treated as a linting rule (Rule `I`), not a formatting rule. You must explicitly select it if it isn't in your config.

```bash
ruff check --select I --fix .

```

---

> **Pro Tip:** You often want to do all of the above at once. You can chain the commands:
> ```bash
> ruff format . && ruff check --select I --fix .
> 
> ```
> 
> 

Would you like me to generate a `pyproject.toml` snippet to make these settings permanent so you don't have to type flags every time?