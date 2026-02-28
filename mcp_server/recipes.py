"""Debugging recipe strings for MCP prompt definitions.

Each recipe is a structured workflow that guides Claude through a GPU debugging scenario.
"""

RECIPE_INVISIBLE_OBJECT = """\
# Recipe: Object is Invisible

**Symptoms**: An object that should be visible in the scene is not rendered.

## Steps

1. Open the capture:
   `rdc_session(action="open", capture="path/to/frame.rdc")`

2. List all draws to find the expected object:
   `rdc_draws(flags="--json --limit 50")`

3. If you know the pass name, filter:
   `rdc_draws(flags="--pass 'Raster Pass' --json")`

4. Check rasterizer state — is back-face culling removing it?
   `rdc_pipeline(eid=EID, section="rs", flags="--json")`
   - Look for: CullMode, FrontFace, Viewports, ScissorRects

5. Check depth state:
   `rdc_pipeline(eid=EID, section="ds", flags="--json")`

6. Verify the draw is issuing geometry:
   `rdc_draws(eid=EID, flags="--json")`
   - Expected: VertexCount > 0, InstanceCount > 0

7. Debug a vertex to check transform:
   `rdc_pixel(action="debug vertex", eid=EID, args="0 --json")`
   - Look at gl_Position / SV_Position — is it in NDC [-1,1]?

## Common Causes
- CullMode is Front when geometry has clockwise winding (or vice versa)
- Viewport is zero-sized or doesn't cover the object
- Scissor rect clips the object
- Depth test rejects it (object behind another or outside depth range)
- Blend state has ColorWriteMask: 0 (writing disabled)
- Vertex transform puts vertices off-screen
"""

RECIPE_WRONG_COLORS = """\
# Recipe: Colors Are Wrong

**Symptoms**: Object renders but with incorrect colors, wrong texture, or unexpected tint.

## Steps

1. Export what we see:
   `rdc_export(action="rt", eid=EID, output="analysis/wrong_color.png")`

2. Pick the pixel to check its value:
   `rdc_pixel(action="pick-pixel", eid=EID, args="256 256 --json")`

3. Check bound textures:
   `rdc_pipeline(eid=EID, action="bindings", flags="--json")`
   - Look for sampler2D / texture2D bindings, verify resource IDs

4. Export the bound texture to verify it's correct:
   `rdc_export(action="texture", resource_id=RESID, output="analysis/bound_tex.png")`

5. Check constant buffers for material colors:
   `rdc_shader(eid=EID, stage="ps", flags="--constants --json")`

6. Check blend state:
   `rdc_pipeline(eid=EID, section="om", flags="--json")`

7. If still unclear, trace the pixel shader:
   `rdc_pixel(action="debug pixel", eid=EID, args="256 256 --trace")`

## Common Causes
- Wrong texture bound (check resource ID matches expected)
- Constant buffer has wrong material color
- Blend state is additive (Source: One, Dest: One) when it should be alpha
- Texture format mismatch (sRGB vs linear, swizzled channels)
- Fragment shader has hardcoded color or wrong calculation
"""

RECIPE_BROKEN_SHADOWS = """\
# Recipe: Shadows Are Broken

**Symptoms**: Shadows are too dark, too blocky, have peter-panning, acne, or are missing entirely.

## Steps

1. List passes to confirm structure:
   `rdc_overview(action="passes", flags="--json")`

2. Find shadow pass draws:
   `rdc_draws(flags="--pass 'Shadow Pass' --json")`

3. Export the shadow map (use the last shadow pass draw EID):
   `rdc_export(action="rt", eid=SHADOW_EID, output="analysis/shadow_map.png")`
   - Look for: resolution, coverage, depth range

4. Check shadow map resolution via bindings:
   `rdc_pipeline(eid=SHADOW_EID, action="bindings", flags="--json")`
   - Look at render target dimensions

5. Check depth bias (prevents shadow acne):
   `rdc_pipeline(eid=SHADOW_EID, section="rs", flags="--json")`
   - Shadow acne: DepthBias too low (or zero)
   - Peter-panning: DepthBias too high

6. Check the fragment shader for shadow sampling:
   `rdc_shader(eid=LIGHT_EID, stage="ps", flags="--source")`
   - Look for: shadow map sampling, bias, PCF kernel

7. Check light matrices and shadow parameters:
   `rdc_shader(eid=LIGHT_EID, stage="ps", flags="--constants --json")`
   - Look for: lightViewProj, shadowBias, shadowMapSize

8. Debug a pixel that should be in shadow:
   `rdc_pixel(action="debug pixel", eid=LIGHT_EID, args="300 400 --trace")`

## Common Issues
| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| Blocky/pixelated | Low shadow map resolution | bindings -> RT dimensions |
| Acne (self-shadowing) | Depth bias too low | pipeline rs -> DepthBias |
| Peter-panning (detached) | Depth bias too high | pipeline rs -> DepthBias |
| Missing entirely | Shadow map not sampled | bindings on raster pass |
| Wrong direction | Light matrix incorrect | shader constants -> lightViewProj |
| Hard edges | No PCF / PCF radius = 0 | shader source -> PCF code |
"""

RECIPE_PERFORMANCE = """\
# Recipe: Performance Is Bad

**Symptoms**: Low FPS, high GPU utilization, large frame time.

## Steps

1. Get frame statistics:
   `rdc_overview(action="stats", flags="--json")`
   - Look for: total draws, total events, per-pass breakdown

2. Check draw count per pass:
   `rdc_overview(action="passes", flags="--json")`
   - Excessive draws in any single pass?

3. Check for massive textures:
   `rdc_resources(action="resources", flags="--type Texture --sort size --json")`
   - Textures > 16MB may indicate uncompressed or oversized

4. Look for redundant state changes:
   `rdc_draws(flags="--limit 200 --json")`

5. Check for overdraw with wireframe overlay:
   `rdc_export(action="rt", eid=EID, output="analysis/wireframe.png", flags="--overlay wireframe")`
   - Dense wireframe = high geometric complexity

## Performance Red Flags
- Draw count > 1000 per pass (consider batching/instancing)
- Textures > 32MB (consider compression, mipmaps)
- Multiple passes with identical draw calls (redundant work)
- Many small draws with state changes between each
"""

RECIPE_COMPARE_FRAMES = """\
# Recipe: What Changed Between Two Frames

**Symptoms**: Regression between two builds, or before/after a code change.

## Steps

1. Quick summary:
   `rdc_diff(capture_a="before.rdc", capture_b="after.rdc", flags="--shortstat")`

2. Detailed draw comparison:
   `rdc_diff(capture_a="before.rdc", capture_b="after.rdc", flags="--draws --json")`

3. Pass comparison:
   `rdc_diff(capture_a="before.rdc", capture_b="after.rdc", flags="--passes --json")`

4. Resource comparison:
   `rdc_diff(capture_a="before.rdc", capture_b="after.rdc", flags="--resources --json")`

5. Visual diff of final framebuffer:
   `rdc_diff(capture_a="before.rdc", capture_b="after.rdc", flags="--framebuffer --diff-output analysis/diff.png")`
   - Changed pixels will be highlighted

6. Compare pipeline state at a specific draw:
   `rdc_diff(capture_a="before.rdc", capture_b="after.rdc", flags="--pipeline EID --json")`
"""

RECIPE_DEBUG_PIXEL = """\
# Recipe: Debug This Pixel

**Symptoms**: User points at a specific pixel and asks "why does this look like that?"

## Steps

1. Get pixel history — who wrote to this pixel?
   `rdc_pixel(action="pixel", eid=EID, args="X Y --json")`
   - Shows every draw that touched this pixel, with pass/fail and pre/post colors

2. Go to the draw that produced the final color (last passing entry):
   `rdc_pixel(action="pick-pixel", eid=FINAL_EID, args="X Y --json")`

3. Get the shader execution summary:
   `rdc_pixel(action="debug pixel", eid=FINAL_EID, args="X Y --json")`

4. If you need the full trace:
   `rdc_pixel(action="debug pixel", eid=FINAL_EID, args="X Y --trace")`

5. Check specific variable values at a line:
   `rdc_pixel(action="debug pixel", eid=FINAL_EID, args="X Y --dump-at 15")`
   - Shows all variable values when execution reaches line 15

6. Cross-reference with pipeline state:
   `rdc_pipeline(eid=FINAL_EID, flags="--json")`

7. Export the render target at that draw to see context:
   `rdc_export(action="rt", eid=FINAL_EID, output="analysis/at_draw.png")`

## Interpretation Guide
- pixel history shows passed: false with depth_test — object is behind something
- pixel history shows passed: false with stencil_test — stencil mask is blocking
- final color differs from shader output — blend state is modifying it
- no entries in pixel history — nothing is drawing to that pixel (check viewport/scissor)
"""
