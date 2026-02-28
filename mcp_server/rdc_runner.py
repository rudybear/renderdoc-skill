"""Async subprocess wrapper for rdc-cli commands.

All output goes to stderr — stdout is reserved for MCP JSON-RPC transport.
"""

import asyncio
import json
import os
import shutil
import sys


def _find_rdc() -> str:
    """Find the rdc executable."""
    # Check PATH
    rdc = shutil.which("rdc")
    if rdc:
        return rdc
    # Fallback: try common pip Scripts locations on Windows
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    candidate = os.path.join(scripts_dir, "rdc.exe")
    if os.path.exists(candidate):
        return candidate
    candidate = os.path.join(scripts_dir, "rdc")
    if os.path.exists(candidate):
        return candidate
    return "rdc"  # Last resort, let PATH resolve it


RDC_EXE = _find_rdc()


async def run_rdc(
    args: list[str],
    timeout: float = 60.0,
) -> dict:
    """Run an rdc-cli command and return structured output.

    Args:
        args: Command arguments (e.g., ["open", "path/to/file.rdc"]).
        timeout: Timeout in seconds.

    Returns:
        dict with keys:
          - ok (bool): True if exit code was 0.
          - output (str): Captured stdout text.
          - error (str): Captured stderr text.
          - data (dict|list|None): Parsed JSON if --json was in args.
          - exit_code (int): Process exit code.
    """
    env = os.environ.copy()
    # Prevent MSYS2/Git Bash from mangling /paths to C:/Program Files/Git/...
    env["MSYS_NO_PATHCONV"] = "1"
    # Ensure UTF-8 output (rdc-cli uses emoji which fails on cp1252)
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [RDC_EXE] + args

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return {
            "ok": False,
            "output": "",
            "error": f"Command timed out after {timeout}s: rdc {' '.join(args)}",
            "data": None,
            "exit_code": -1,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "output": "",
            "error": "rdc-cli not found. Install with: pip install rdc-cli",
            "data": None,
            "exit_code": -1,
        }

    stdout_text = stdout_bytes.decode("utf-8", errors="replace")
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")
    exit_code = proc.returncode or 0

    # Log to stderr (never stdout — sacred for MCP JSON-RPC)
    if stderr_text.strip():
        print(f"[rdc stderr] {stderr_text.strip()}", file=sys.stderr)

    # Parse JSON if --json flag was used
    data = None
    if "--json" in args and stdout_text.strip():
        try:
            data = json.loads(stdout_text)
        except json.JSONDecodeError:
            pass  # Return raw text; caller can handle it

    return {
        "ok": exit_code == 0,
        "output": stdout_text,
        "error": stderr_text,
        "data": data,
        "exit_code": exit_code,
    }


def format_result(result: dict) -> str:
    """Format a run_rdc result into a human-readable string for MCP tool output."""
    if not result["ok"]:
        msg = result["error"].strip() or result["output"].strip()
        return f"Error (exit code {result['exit_code']}):\n{msg}"

    if result["data"] is not None:
        return json.dumps(result["data"], indent=2)

    return result["output"].strip()
