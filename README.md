# renderdoc-skill

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill that gives Claude the ability to capture, inspect, and debug GPU frames using [RenderDoc](https://renderdoc.org). Works with Vulkan, D3D11, D3D12, and OpenGL.

## Demo

[![Watch the demo](https://img.youtube.com/vi/UkaXPtCWwo4/maxresdefault.jpg)](https://www.youtube.com/watch?v=UkaXPtCWwo4)

## What This Does

This skill teaches Claude Code how to do GPU debugging. When you describe a rendering problem — broken shadows, wrong colors, missing objects, performance issues — Claude can:

- **Capture GPU frames** from your application using RenderDoc's Python API
- **Inspect pipeline state** at any draw call (shaders, blend, depth, rasterizer, bindings)
- **Export and view render targets** as PNGs (Claude is multimodal — it can see your framebuffer)
- **Debug shaders** line-by-line, tracing pixel/vertex/compute execution
- **Trace pixel history** to find which draw wrote a color and why
- **Edit and replay shaders** without recompiling your application
- **Compare frames** side-by-side to find regressions

It works through [`rdc-cli`](https://github.com/BANANASJIM/rdc-cli), a 66-command CLI that wraps RenderDoc's Python API into shell commands that Claude Code can call.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| [RenderDoc](https://renderdoc.org) | Need `renderdoc.pyd` + `renderdoc.dll` (from RenderDoc install or built from source) |
| Python 3.10+ | Must match the Python version `renderdoc.pyd` was built against |
| [rdc-cli](https://github.com/BANANASJIM/rdc-cli) | `pip install rdc-cli` |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | Anthropic's CLI agent |

## Installation

### 1. Clone this repo into your project

```bash
# Option A: Clone into your project directory
cd /path/to/your/project
git clone https://github.com/rudybear/renderdoc-skill .claude/skills/renderdoc-gpu-debug

# Option B: Clone standalone and copy the skill files
git clone https://github.com/rudybear/renderdoc-skill
cp -r renderdoc-skill/.claude/skills/renderdoc-gpu-debug /path/to/your/project/.claude/skills/
```

### 2. Install rdc-cli

```bash
pip install rdc-cli
```

### 3. Set up RenderDoc module path

Set `RENDERDOC_PYTHON_PATH` to the directory containing `renderdoc.pyd` and `renderdoc.dll`:

```bash
# In your shell profile (.bashrc, .zshrc, etc.)
export RENDERDOC_PYTHON_PATH=/path/to/renderdoc/module
```

If you installed RenderDoc from the official installer, this is typically:
- **Windows**: `C:/Program Files/RenderDoc/`
- **Linux**: `/usr/lib/renderdoc/` or wherever you built it

### 4. Register the Vulkan layer (Vulkan apps only)

For Vulkan capture, the RenderDoc implicit layer must be registered:

- **Windows**: Add `renderdoc.json` to `HKCU\SOFTWARE\Khronos\Vulkan\ImplicitLayers` (DWORD 0)
- **Linux**: Copy `renderdoc.json` to `~/.local/share/vulkan/implicit_layer.d/`

Also set: `export ENABLE_VULKAN_RENDERDOC_CAPTURE=1`

### 5. Verify

```bash
rdc doctor
```

All checks should pass.

### 6. Customize CLAUDE.md

Edit the `CLAUDE.md` in this repo to fill in your project-specific paths (application executable, working directory, capture output directory). This tells Claude about your specific setup.

## How It Works

### Skill trigger

Claude Code loads skills based on YAML frontmatter keywords. When you mention GPU debugging, RenderDoc, shaders, render targets, pipeline state, or visual glitches, Claude activates this skill and gains access to the full `rdc-cli` command vocabulary.

### Session lifecycle

Every inspection session follows open-work-close:

```bash
rdc open path/to/capture.rdc   # Load a capture
# ... inspection commands ...
rdc close                       # Release GPU resources
```

### Visual inspection pattern

Claude can see images. The core debugging loop is:

1. **Export** a render target or texture to PNG (`rdc rt EID -o output.png`)
2. **View** it using Claude Code's Read tool (multimodal — Claude sees the image)
3. **Correlate** with pipeline state data (`rdc pipeline`, `rdc shader`, `rdc bindings`)
4. **Diagnose** the issue and suggest fixes

### Included debugging recipes

The skill includes 6 ready-made debugging workflows:

1. **Object is invisible** — culling, depth, blend, vertex transform checks
2. **Colors are wrong** — texture bindings, constants, blend state, shader trace
3. **Shadows are broken** — shadow map export, depth bias, light matrices, PCF
4. **Performance is bad** — draw counts, resource sizes, overdraw, GPU counters
5. **What changed between frames** — frame diff with visual comparison
6. **Debug this pixel** — pixel history, shader trace, variable inspection

## File Structure

```
.claude/skills/renderdoc-gpu-debug/
  SKILL.md                          # Main skill (loaded by Claude Code)
  references/
    commands-quick-ref.md           # All 66 rdc-cli commands with args/options
    debugging-recipes.md            # 6 extended debugging workflows

CLAUDE.md                           # Project context (customize for your app)
capture_frame.py                    # Example: capture a frame via RenderDoc Python API
```

## Example Usage

Once installed, just talk to Claude Code naturally:

```
> The shadows in my scene look blocky and have acne artifacts. Can you debug it?

> Capture a frame and show me what the shadow map looks like.

> Why is the sphere rendering black? It should be red.

> Compare these two captures and tell me what changed.

> Debug pixel (256, 300) — why is it transparent?
```

Claude will use `rdc-cli` commands, export PNGs to inspect visually, check pipeline state, and trace shader execution to diagnose the issue.

## Acknowledgments

- **[rdc-cli](https://github.com/BANANASJIM/rdc-cli)** by Jim (BANANASJIM) — the 66-command CLI that makes this skill possible. MIT license.
- **[RenderDoc](https://renderdoc.org)** by Baldur Karlsson — the GPU debugger that powers everything underneath. MIT license.
- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** by Anthropic — the AI coding agent that runs the skill.

## License

MIT. See [LICENSE](LICENSE).
