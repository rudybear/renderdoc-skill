"""RenderDoc MCP Server — exposes rdc-cli as MCP tools for Claude Code.

Run with:  python mcp_server/server.py
Register:  claude mcp add rdc-tools -- python D:/renderdoc/mcp_server/server.py

stdout is sacred (JSON-RPC transport) — all logging goes to stderr.
"""

import base64
import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from rdc_runner import run_rdc, format_result
from recipes import (
    RECIPE_INVISIBLE_OBJECT,
    RECIPE_WRONG_COLORS,
    RECIPE_BROKEN_SHADOWS,
    RECIPE_PERFORMANCE,
    RECIPE_COMPARE_FRAMES,
    RECIPE_DEBUG_PIXEL,
)

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "rdc-tools",
    instructions="GPU frame debugging with RenderDoc via rdc-cli. "
    "Use rdc_session to open/close captures, then inspect with the other tools.",
)

CAPTURES_DIR = Path(os.environ.get("RDC_CAPTURES_DIR", "./captures"))
ANALYSIS_DIR = CAPTURES_DIR / "analysis"
IMAGE_SIZE_LIMIT = 5 * 1024 * 1024  # 5 MB inline limit

NO_SESSION_MSG = (
    "No capture is open. Use rdc_session(action='open', "
    "capture='path/to/file.rdc') first."
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _maybe_inline_image(path: str) -> str | None:
    """Return base64 data URI if file exists and is under size limit."""
    p = Path(path)
    if not p.exists() or not p.suffix.lower() == ".png":
        return None
    if p.stat().st_size > IMAGE_SIZE_LIMIT:
        return None
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ===========================================================================
# TOOLS (13)
# ===========================================================================

@mcp.tool()
async def rdc_session(
    action: str,
    capture: str = "",
    flags: str = "",
) -> str:
    """Manage RenderDoc capture sessions.

    Args:
        action: One of "open", "close", or "status".
        capture: Path to .rdc file (required for "open").
        flags: Extra flags (e.g., "--preload", "--shutdown").
    """
    if action == "open":
        if not capture:
            return "Error: 'capture' path is required for action='open'."
        args = ["open", capture] + flags.split()
        result = await run_rdc(args)
        return format_result(result)
    elif action == "close":
        args = ["close"] + flags.split()
        result = await run_rdc(args)
        return format_result(result)
    elif action == "status":
        result = await run_rdc(["status"])
        return format_result(result)
    else:
        return f"Unknown action '{action}'. Use 'open', 'close', or 'status'."


@mcp.tool()
async def rdc_overview(
    action: str,
    flags: str = "",
) -> str:
    """Get capture overview information.

    Args:
        action: One of "info", "stats", "passes", "count", "gpus".
        flags: Extra flags (e.g., "--json", "--pass 'Shadow Pass'").
    """
    valid = {"info", "stats", "passes", "count", "gpus"}
    if action not in valid:
        return f"Unknown action '{action}'. Use one of: {', '.join(sorted(valid))}."
    args = [action] + flags.split()
    result = await run_rdc(args)
    return format_result(result)


@mcp.tool()
async def rdc_draws(
    eid: int | None = None,
    flags: str = "",
) -> str:
    """List or inspect draw calls.

    Args:
        eid: Optional event ID for a single draw detail (uses "draw EID").
             Omit to list draws (uses "draws").
        flags: Extra flags (e.g., "--json", "--pass 'Shadow Pass'", "--limit 50").
    """
    extra = flags.split() if flags else []
    if eid is not None:
        args = ["draw", str(eid)] + extra
    else:
        # Default limit to prevent huge output
        if "--limit" not in flags:
            extra += ["--limit", "50"]
        args = ["draws"] + extra
    result = await run_rdc(args)
    return format_result(result)


@mcp.tool()
async def rdc_events(
    eid: int | None = None,
    flags: str = "",
) -> str:
    """List or inspect API events.

    Args:
        eid: Optional event ID for a single event detail.
             Omit to list events.
        flags: Extra flags (e.g., "--json", "--type draw", "--limit 100").
    """
    extra = flags.split() if flags else []
    if eid is not None:
        args = ["event", str(eid)] + extra
    else:
        if "--limit" not in flags:
            extra += ["--limit", "50"]
        args = ["events"] + extra
    result = await run_rdc(args)
    return format_result(result)


@mcp.tool()
async def rdc_pipeline(
    eid: int | None = None,
    section: str = "",
    action: str = "pipeline",
    flags: str = "",
) -> str:
    """Inspect pipeline state or resource bindings.

    Args:
        eid: Event ID (uses current if omitted).
        section: Pipeline section (e.g., "rs", "om", "ds", "vs", "ps").
        action: "pipeline" (default) or "bindings".
        flags: Extra flags (e.g., "--json", "--set 0", "--binding 1").
    """
    extra = flags.split() if flags else []
    if action == "bindings":
        args = ["bindings"]
        if eid is not None:
            args.append(str(eid))
        args += extra
    else:
        args = ["pipeline"]
        if eid is not None:
            args.append(str(eid))
        if section:
            args.append(section)
        args += extra
    result = await run_rdc(args)
    return format_result(result)


@mcp.tool()
async def rdc_shader(
    eid: int | None = None,
    stage: str = "",
    flags: str = "",
) -> str:
    """Inspect shaders — metadata, source, constants, reflection, or search.

    Args:
        eid: Event ID (for shader inspection at a specific draw).
        stage: Shader stage (e.g., "vs", "ps", "cs").
        flags: Extra flags. Key flags:
               --source (show source), --constants (show uniforms),
               --reflect (show inputs/outputs), --json, --targets.
               For listing: omit eid/stage and add --json to call "shaders".
               For search: use flags="search PATTERN --json".
               For shader-map: use flags="shader-map --json".
    """
    extra = flags.split() if flags else []

    # Special sub-commands routed through flags
    if extra and extra[0] == "search":
        args = ["search"] + extra[1:]
        result = await run_rdc(args)
        return format_result(result)

    if extra and extra[0] == "shader-map":
        args = ["shader-map"] + extra[1:]
        result = await run_rdc(args)
        return format_result(result)

    if extra and extra[0] == "shaders":
        args = ["shaders"] + extra[1:]
        result = await run_rdc(args)
        return format_result(result)

    # Default: shader EID STAGE [flags]
    args = ["shader"]
    if eid is not None:
        args.append(str(eid))
    if stage:
        args.append(stage)
    args += extra
    result = await run_rdc(args)
    return format_result(result)


@mcp.tool()
async def rdc_export(
    action: str,
    eid: int | None = None,
    resource_id: int | None = None,
    output: str = "",
    flags: str = "",
) -> str:
    """Export visual data — render targets, textures, thumbnails, meshes, buffers.

    Returns the file path and, for PNG images under 5MB, an inline base64 image.

    Args:
        action: One of "rt", "texture", "thumbnail", "mesh", "buffer".
        eid: Event ID (for "rt" and "mesh").
        resource_id: Resource ID (for "texture" and "buffer").
        output: Output file path. Auto-generated if omitted.
        flags: Extra flags (e.g., "--overlay wireframe", "--mip 0", "--target 1").
    """
    extra = flags.split() if flags else []

    # Auto-generate output path
    if not output and action in ("rt", "texture", "thumbnail"):
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        if action == "rt":
            output = str(ANALYSIS_DIR / f"rt_{eid or 'current'}.png")
        elif action == "texture":
            output = str(ANALYSIS_DIR / f"tex_{resource_id or 'unknown'}.png")
        elif action == "thumbnail":
            output = str(ANALYSIS_DIR / "thumbnail.png")
    elif not output and action == "mesh":
        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        output = str(ANALYSIS_DIR / f"mesh_{eid or 'current'}.obj")

    if action == "rt":
        args = ["rt"]
        if eid is not None:
            args.append(str(eid))
        if output:
            args += ["-o", output]
        args += extra

    elif action == "texture":
        if resource_id is None:
            return "Error: 'resource_id' is required for action='texture'."
        args = ["texture", str(resource_id)]
        if output:
            args += ["-o", output]
        args += extra

    elif action == "thumbnail":
        args = ["thumbnail"]
        if output:
            args += ["-o", output]
        args += extra

    elif action == "mesh":
        args = ["mesh"]
        if eid is not None:
            args.append(str(eid))
        if output:
            args += ["-o", output]
        args += extra

    elif action == "buffer":
        if resource_id is None:
            return "Error: 'resource_id' is required for action='buffer'."
        args = ["buffer", str(resource_id)]
        if output:
            args += ["-o", output]
        args += extra

    else:
        return f"Unknown action '{action}'. Use: rt, texture, thumbnail, mesh, buffer."

    result = await run_rdc(args)
    text = format_result(result)

    # Attach inline image if applicable
    if result["ok"] and output:
        inline = _maybe_inline_image(output)
        if inline:
            text += f"\n\nImage saved to: {output}\n![export]({inline})"
        else:
            text += f"\n\nFile saved to: {output}"

    return text


@mcp.tool()
async def rdc_pixel(
    action: str,
    eid: int | None = None,
    args: str = "",
) -> str:
    """Pixel debugging — history, pick, debug pixel/vertex/thread.

    Args:
        action: One of "pixel", "pick-pixel", "debug pixel", "debug vertex", "debug thread".
        eid: Event ID.
        args: Positional args as a string (e.g., "256 256 --json" for coordinates and flags).
    """
    extra = args.split() if args else []

    if action == "pixel":
        cmd = ["pixel"]
        if extra:
            cmd += extra
        if eid is not None:
            # pixel X Y [EID] — insert EID after coordinates
            # If extra has at least 2 items (x, y), insert eid after them
            if len(extra) >= 2:
                cmd = ["pixel", extra[0], extra[1], str(eid)] + extra[2:]
            else:
                cmd = ["pixel"] + extra + [str(eid)]
        result = await run_rdc(cmd)

    elif action == "pick-pixel":
        cmd = ["pick-pixel"]
        if extra:
            cmd += extra
        if eid is not None and len(extra) >= 2:
            cmd = ["pick-pixel", extra[0], extra[1], str(eid)] + extra[2:]
        elif eid is not None:
            cmd = ["pick-pixel"] + extra + [str(eid)]
        result = await run_rdc(cmd)

    elif action == "debug pixel":
        cmd = ["debug", "pixel"]
        if eid is not None:
            cmd.append(str(eid))
        cmd += extra
        result = await run_rdc(cmd)

    elif action == "debug vertex":
        cmd = ["debug", "vertex"]
        if eid is not None:
            cmd.append(str(eid))
        cmd += extra
        result = await run_rdc(cmd)

    elif action == "debug thread":
        cmd = ["debug", "thread"]
        if eid is not None:
            cmd.append(str(eid))
        cmd += extra
        result = await run_rdc(cmd)

    else:
        return (
            f"Unknown action '{action}'. Use: pixel, pick-pixel, "
            "debug pixel, debug vertex, debug thread."
        )

    return format_result(result)


@mcp.tool()
async def rdc_diff(
    capture_a: str,
    capture_b: str,
    flags: str = "",
) -> str:
    """Compare two RenderDoc captures.

    Args:
        capture_a: Path to first .rdc capture.
        capture_b: Path to second .rdc capture.
        flags: Comparison flags (e.g., "--shortstat", "--draws --json",
               "--framebuffer --diff-output analysis/diff.png").
    """
    extra = flags.split() if flags else []
    args = ["diff", capture_a, capture_b] + extra
    result = await run_rdc(args, timeout=120.0)
    text = format_result(result)

    # Check for diff image output
    if "--diff-output" in flags:
        idx = extra.index("--diff-output")
        if idx + 1 < len(extra):
            diff_path = extra[idx + 1]
            inline = _maybe_inline_image(diff_path)
            if inline:
                text += f"\n\n![diff]({inline})"

    return text


@mcp.tool()
async def rdc_resources(
    action: str = "resources",
    resource_id: int | None = None,
    flags: str = "",
) -> str:
    """Inspect GPU resources — list, detail, usage, texture stats.

    Args:
        action: One of "resources", "resource", "usage", "tex-stats".
        resource_id: Resource ID (required for "resource", "usage", "tex-stats").
        flags: Extra flags (e.g., "--json", "--type Texture", "--sort size").
    """
    extra = flags.split() if flags else []

    if action == "resources":
        args = ["resources"] + extra
    elif action == "resource":
        if resource_id is None:
            return "Error: 'resource_id' is required for action='resource'."
        args = ["resource", str(resource_id)] + extra
    elif action == "usage":
        args = ["usage"]
        if resource_id is not None:
            args.append(str(resource_id))
        args += extra
    elif action == "tex-stats":
        if resource_id is None:
            return "Error: 'resource_id' is required for action='tex-stats'."
        args = ["tex-stats", str(resource_id)] + extra
    else:
        return f"Unknown action '{action}'. Use: resources, resource, usage, tex-stats."

    result = await run_rdc(args)
    return format_result(result)


@mcp.tool()
async def rdc_shader_edit(
    action: str,
    eid: int | None = None,
    stage: str = "",
    flags: str = "",
) -> str:
    """Shader edit-replay — build, replace, restore shaders.

    Args:
        action: One of "shader-build", "shader-replace", "shader-restore",
                "shader-restore-all", "shader-encodings".
        eid: Event ID (for replace/restore).
        stage: Shader stage (for replace/restore, e.g., "ps", "vs").
        flags: Extra flags (e.g., "source.glsl --encoding GLSL" for build,
               "--with 123" for replace).
    """
    extra = flags.split() if flags else []

    if action == "shader-build":
        args = ["shader-build"] + extra
    elif action == "shader-replace":
        if eid is None or not stage:
            return "Error: 'eid' and 'stage' are required for shader-replace."
        args = ["shader-replace", str(eid), stage] + extra
    elif action == "shader-restore":
        if eid is None or not stage:
            return "Error: 'eid' and 'stage' are required for shader-restore."
        args = ["shader-restore", str(eid), stage] + extra
    elif action == "shader-restore-all":
        args = ["shader-restore-all"] + extra
    elif action == "shader-encodings":
        args = ["shader-encodings"] + extra
    else:
        return (
            f"Unknown action '{action}'. Use: shader-build, shader-replace, "
            "shader-restore, shader-restore-all, shader-encodings."
        )

    result = await run_rdc(args)
    return format_result(result)


@mcp.tool()
async def rdc_capture(
    action: str = "capture",
    flags: str = "",
) -> str:
    """Frame capture — capture, attach, trigger, list, copy.

    Args:
        action: One of "capture", "attach", "capture-trigger",
                "capture-list", "capture-copy".
        flags: All arguments as a string. Examples:
               capture: "-o captures/frame.rdc -- ./app --args"
               attach: "12345 --host localhost"
               capture-trigger: "--num-frames 1"
               capture-list: "--json"
               capture-copy: "0 dest.rdc"
    """
    valid = {"capture", "attach", "capture-trigger", "capture-list", "capture-copy"}
    if action not in valid:
        return f"Unknown action '{action}'. Use one of: {', '.join(sorted(valid))}."

    extra = flags.split() if flags else []
    args = [action] + extra
    result = await run_rdc(args, timeout=120.0)
    return format_result(result)


@mcp.tool()
async def rdc_vfs(
    action: str = "ls",
    path: str = "",
    flags: str = "",
) -> str:
    """Browse the capture's virtual filesystem.

    Args:
        action: One of "ls", "tree", "cat".
        path: VFS path (e.g., "/", "/textures/0").
        flags: Extra flags (e.g., "--json", "--depth 3", "-l", "-F").
    """
    valid = {"ls", "tree", "cat"}
    if action not in valid:
        return f"Unknown action '{action}'. Use one of: {', '.join(sorted(valid))}."

    extra = flags.split() if flags else []
    args = [action]
    if path:
        args.append(path)
    args += extra
    result = await run_rdc(args)
    return format_result(result)


@mcp.tool()
async def rdc_command(
    command: str,
    flags: str = "",
) -> str:
    """Run any rdc-cli command directly (generic fallback).

    Use this for commands not covered by the specialized tools:
    assert-clean, assert-count, assert-image, assert-pixel, assert-state,
    log, goto, doctor, counters, script, snapshot, sections, pass, etc.

    Args:
        command: The rdc sub-command (e.g., "doctor", "log", "goto").
        flags: All arguments and flags as a string.
    """
    extra = flags.split() if flags else []
    args = [command] + extra
    result = await run_rdc(args)
    return format_result(result)


# ===========================================================================
# RESOURCES (2)
# ===========================================================================

@mcp.resource("rdc://captures")
async def list_captures() -> str:
    """List .rdc capture files in the captures directory."""
    if not CAPTURES_DIR.exists():
        return json.dumps({"captures": [], "directory": str(CAPTURES_DIR)})

    captures = sorted(CAPTURES_DIR.glob("*.rdc"), key=lambda p: p.stat().st_mtime, reverse=True)
    items = []
    for c in captures[:50]:  # Limit to 50 most recent
        stat = c.stat()
        items.append({
            "name": c.name,
            "path": str(c),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": stat.st_mtime,
        })

    return json.dumps({"captures": items, "directory": str(CAPTURES_DIR)}, indent=2)


@mcp.resource("rdc://captures/{name}")
async def get_capture_metadata(name: str) -> str:
    """Get metadata for a specific capture file."""
    capture_path = CAPTURES_DIR / name
    if not capture_path.exists():
        return json.dumps({"error": f"Capture not found: {name}"})

    # Get file info
    stat = capture_path.stat()
    info = {
        "name": name,
        "path": str(capture_path),
        "size_mb": round(stat.st_size / (1024 * 1024), 2),
    }

    # Try to get rdc metadata
    result = await run_rdc(["open", str(capture_path)])
    if result["ok"]:
        meta_result = await run_rdc(["info", "--json"])
        if meta_result["data"]:
            info["metadata"] = meta_result["data"]
        await run_rdc(["close"])

    return json.dumps(info, indent=2)


# ===========================================================================
# PROMPTS (6)
# ===========================================================================

@mcp.prompt()
async def debug_invisible_object() -> str:
    """Workflow: debug an object that should be visible but isn't rendering."""
    return RECIPE_INVISIBLE_OBJECT


@mcp.prompt()
async def debug_wrong_colors() -> str:
    """Workflow: debug incorrect colors, wrong textures, or unexpected tint."""
    return RECIPE_WRONG_COLORS


@mcp.prompt()
async def debug_broken_shadows() -> str:
    """Workflow: debug shadow artifacts — acne, peter-panning, blocky, or missing shadows."""
    return RECIPE_BROKEN_SHADOWS


@mcp.prompt()
async def debug_performance() -> str:
    """Workflow: investigate GPU performance issues — high draw counts, overdraw, large textures."""
    return RECIPE_PERFORMANCE


@mcp.prompt()
async def compare_frames() -> str:
    """Workflow: compare two captures to find what changed (regressions, before/after)."""
    return RECIPE_COMPARE_FRAMES


@mcp.prompt()
async def debug_pixel() -> str:
    """Workflow: trace why a specific pixel has its current color."""
    return RECIPE_DEBUG_PIXEL


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
