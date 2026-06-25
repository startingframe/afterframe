# Afterframe

**Blender → After Effects.** Export your active Blender camera and selected objects (as nulls — with full
position *and* rotation) to a single self-contained `.jsx` that rebuilds the scene in After Effects: the
camera move, lens, and animation matched per frame.

Made by [Starting Frame](https://startingframe.com).

---

## What it does

- Exports the **active camera** — position, orientation, and lens (zoom), animated per frame.
- Exports **selected objects (or all, or all empties)** as **3D nulls** carrying position **and** rotation,
  so they track moves *and* spins.
- Writes **one self-contained `.jsx`** — all the math is baked in Blender; the script just builds the comp.
  No plugins, no dependencies.
- Builds the comp at your **render resolution / fps**, with a `BLENDER_WORLD` parent null so Blender's
  origin = comp center.
- Camera rotation is **render-match validated** and continuity-correct (no mid-move flips on big rotations).

## Install

1. Download **`afterframe-free-v0.1.0.zip`** from [Releases](../../releases).
2. Blender → **Edit ▸ Preferences ▸ Add-ons ▸ Install…** → pick the zip → enable **Afterframe**.
3. The panel appears in the 3D View **N-panel**, under the **Afterframe** tab.

## Use

1. Set your active scene camera and frame range.
2. Pick **Nulls** (*Selected objects* / *All objects* / *All empties*) and select what you want exported.
3. Set **World Scale** (pixels per Blender unit; 100 is a good default) and **Output** (blank → next to
   your `.blend`, or your Desktop).
4. Click **Export .jsx for After Effects**.
5. In After Effects: **File ▸ Scripts ▸ Run Script File…** → pick the `.jsx`. It builds the comp, the
   camera, and your nulls — parented and keyframed.

## Requirements

- Blender 4.0+
- Adobe After Effects (to run the generated `.jsx`)

## Afterframe Pro

This free version exports the camera + nulls. **Afterframe Pro** adds one-click **screen replacement** —
it seats your replacement content onto a tracked surface (scaled, oriented, anchored, riding the move),
plus automatic plate reconnect/conform. *(Coming to Gumroad.)*

## License

[GPL-3.0-or-later](LICENSE). Blender add-ons link Blender's GPL Python API, so they're GPL too.

---

© Starting Frame
