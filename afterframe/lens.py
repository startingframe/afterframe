"""
lens.py — Blender camera -> After Effects camera Zoom (pixels). PURE MATH (no bpy).

AE drives a camera's field of view off its **Zoom** (the focal length in pixels): an object at the
comp plane is 1:1 when distance == Zoom. We match Blender's HORIZONTAL FOV (AE comps are horizontal-
referenced), accounting for sensor fit + pixel aspect — the same sensor-fit-aware calc proven in the
v0 exporter (kept verbatim; it's AE-correct and on the "do not touch" list).
"""

import math


def ae_zoom_px(comp_w, comp_h, par_x, par_y, lens_mm, sensor_w, sensor_h, sensor_fit):
    """AE camera Zoom in pixels for the given comp + Blender camera.

    comp_w/comp_h : comp pixels.  par_x/par_y : pixel aspect.  lens_mm : focal length.
    sensor_w/sensor_h : mm.  sensor_fit : 'AUTO' | 'HORIZONTAL' | 'VERTICAL'.
    """
    asp_x = comp_w * par_x
    asp_y = comp_h * par_y
    if sensor_fit == 'AUTO':
        fit_h = asp_x >= asp_y
    elif sensor_fit == 'HORIZONTAL':
        fit_h = True
    else:
        fit_h = False

    if fit_h:
        hfov = 2.0 * math.atan(sensor_w / (2.0 * lens_mm))
    else:
        vfov = 2.0 * math.atan(sensor_h / (2.0 * lens_mm))
        hfov = 2.0 * math.atan(math.tan(vfov / 2.0) * (asp_x / asp_y))   # vertical FOV -> horizontal

    return (comp_w / 2.0) / math.tan(hfov / 2.0)
