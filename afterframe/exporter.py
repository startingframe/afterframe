"""
exporter.py — read the Blender scene, bake to world space, build the AE payload + write the .jsx.

Imports bpy (runs only inside Blender). All coordinate/rotation math is the render-match-validated code
in coordinate_ae.py (camera rotation = conjugation + -90 offset + continuity unwrap); lens.py does the AE
zoom. This module samples obj.matrix_world per frame and assembles the camera + nulls payload.
"""

import bpy

from . import coordinate_ae as cae
from . import lens
from . import jsx_writer


def _fps(scene):
    base = scene.render.fps_base if scene.render.fps_base else 1.0
    return scene.render.fps / base


def _resolution(scene):
    r = scene.render
    pct = r.resolution_percentage / 100.0
    return int(round(r.resolution_x * pct)), int(round(r.resolution_y * pct))


def _round(v):
    return [round(x, 4) for x in v] if isinstance(v, (list, tuple)) else round(v, 4)


def _collapse(times, values, eps=1e-4):
    """A per-frame channel -> [[t, value]] keyframes; collapsed to ONE key if constant."""
    first = values[0]

    def close(a, b):
        if isinstance(a, (list, tuple)):
            return all(abs(x - y) <= eps for x, y in zip(a, b))
        return abs(a - b) <= eps

    if all(close(v, first) for v in values):
        return [[round(times[0], 5), _round(first)]]
    return [[round(t, 5), _round(v)] for t, v in zip(times, values)]


def _gather_nulls(context, null_source):
    scene = context.scene
    if null_source == 'ALL':
        objs = [o for o in scene.objects if o.type != 'CAMERA']
    elif null_source == 'EMPTIES':
        objs = [o for o in scene.objects if o.type == 'EMPTY']
    else:
        objs = [o for o in context.selected_objects if o.type != 'CAMERA']
    return [o for o in objs if o is not scene.camera]


def build_payload(context, world_scale, comp_name="", null_source='SELECTED'):
    """Bake the active camera + chosen objects (as oriented nulls) into the jsx_writer payload."""
    scene = context.scene
    cam_obj = scene.camera
    if cam_obj is None or cam_obj.type != 'CAMERA':
        raise RuntimeError("No active scene camera — set one in Scene properties before exporting.")

    null_objs = _gather_nulls(context, null_source)
    w, h = _resolution(scene)
    par_x, par_y = scene.render.pixel_aspect_x, scene.render.pixel_aspect_y
    fps = _fps(scene)
    f0, f1 = scene.frame_start, scene.frame_end
    duration = (f1 - f0 + 1) / fps
    scale = world_scale

    times, cam_pos, cam_eul, cam_zoom = [], [], [], []
    nulls_pos = {o.name: [] for o in null_objs}
    nulls_eul = {o.name: [] for o in null_objs}

    saved = scene.frame_current
    try:
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            times.append((f - f0) / fps)
            m = cam_obj.matrix_world
            p = m.to_translation()
            ax, ay, az = cae.blender_to_ae_position(p.x, p.y, p.z)
            cam_pos.append([ax * scale, ay * scale, az * scale])
            cam_eul.append(tuple(m.to_euler('XYZ')))
            cd = cam_obj.data
            cam_zoom.append(lens.ae_zoom_px(w, h, par_x, par_y,
                                            cd.lens, cd.sensor_width, cd.sensor_height, cd.sensor_fit))
            for o in null_objs:
                mo = o.matrix_world
                q = mo.to_translation()
                nx, ny, nz = cae.blender_to_ae_position(q.x, q.y, q.z)
                nulls_pos[o.name].append([nx * scale, ny * scale, nz * scale])
                nulls_eul[o.name].append(tuple(mo.to_euler('XYZ')))
    finally:
        scene.frame_set(saved)

    cam_ori = cae.bake_orientation_sequence(cam_eul, is_camera=True)
    nulls_ori = {n: cae.bake_orientation_sequence(nulls_eul[n], is_camera=False) for n in nulls_eul}

    return {
        "comp": {"name": comp_name or scene.name, "width": w, "height": h,
                 "pixelAspect": round(par_x / par_y, 6), "fps": fps, "duration": round(duration, 5)},
        "worldNull": {"position": [w / 2.0, h / 2.0, 0.0]},
        "camera": {
            "name": cam_obj.name,
            "position": _collapse(times, cam_pos),
            "orientation": _collapse(times, [list(o) for o in cam_ori]),
            "zoom": _collapse(times, cam_zoom),
        },
        "nulls": [{"name": n,
                   "position": _collapse(times, nulls_pos[n]),
                   "orientation": _collapse(times, [list(o) for o in nulls_ori[n]])} for n in nulls_pos],
    }


def export_scene(context, filepath, world_scale=100.0, comp_name="", null_source='SELECTED'):
    """Build the payload and write the .jsx. Returns (path, n_nulls)."""
    payload = build_payload(context, world_scale, comp_name, null_source)
    if not filepath.lower().endswith(".jsx"):
        filepath += ".jsx"
    jsx_writer.write_jsx(filepath, payload)
    return filepath, len(payload["nulls"])
