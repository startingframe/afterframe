bl_info = {
    "name": "Afterframe — Blender to After Effects (Starting Frame)",
    "author": "Brian Pilgrim / Starting Frame",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-panel > Afterframe",
    "description": "Export the active camera + selected objects (as nulls) to a self-contained .jsx for After Effects.",
    "category": "Import-Export",
}

import os
import bpy

from . import coordinate_ae, lens, jsx_writer, exporter

import importlib
for _m in (coordinate_ae, lens, jsx_writer, exporter):
    importlib.reload(_m)


class AF_Props(bpy.types.PropertyGroup):
    world_scale: bpy.props.FloatProperty(
        name="World Scale", default=100.0, min=0.001,
        description="Pixels per Blender unit. 100 px = 1 BU is a sane default.")
    comp_name: bpy.props.StringProperty(
        name="Comp Name", default="", description="AE comp name (blank = scene name).")
    null_source: bpy.props.EnumProperty(
        name="Nulls",
        items=[('SELECTED', "Selected objects", "Export the objects you've selected (any type)"),
               ('ALL', "All objects", "Export every object in the scene (your 'select all')"),
               ('EMPTIES', "All empties", "Export every empty in the scene")],
        default='SELECTED',
        description="Which objects become AE nulls (the active camera always exports separately).")
    filepath: bpy.props.StringProperty(
        name="Output", subtype='FILE_PATH', default="",
        description="Where to write the .jsx. Blank = next to the .blend (or Desktop if unsaved).")


def _resolve_path(props):
    raw = props.filepath.strip()
    name = (props.comp_name.strip() or "afterframe")
    if raw:
        path = bpy.path.abspath(raw)
    elif bpy.data.filepath:
        path = os.path.dirname(bpy.data.filepath)
    else:
        path = os.path.expanduser("~/Desktop")
    if path.startswith("//") or not os.path.isabs(path):
        path = os.path.expanduser("~/Desktop")
    if path.endswith(os.sep) or os.path.isdir(path):
        path = os.path.join(path, name + ".jsx")
    return path


class AF_OT_export(bpy.types.Operator):
    bl_idname = "afterframe.export"
    bl_label = "Export .jsx for After Effects"
    bl_description = "Bake the active camera + selected objects to a self-contained .jsx"

    def execute(self, context):
        props = context.window_manager.afterframe
        try:
            path = _resolve_path(props)
            out, n = exporter.export_scene(context, path, props.world_scale, props.comp_name, props.null_source)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, "Afterframe export failed: %s" % e)
            return {'CANCELLED'}
        self.report({'INFO'}, "Afterframe: exported %s  (%d nulls)" % (out, n))
        return {'FINISHED'}


class AF_PT_panel(bpy.types.Panel):
    bl_label = "Afterframe"
    bl_idname = "AF_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Afterframe"

    def draw(self, context):
        p = context.window_manager.afterframe
        col = self.layout.column(align=True)
        col.prop(p, "world_scale")
        col.prop(p, "comp_name")
        col.prop(p, "null_source")
        col.prop(p, "filepath")
        col.separator()
        col.operator("afterframe.export", icon='EXPORT')
        col.label(text="Active cam = camera. Nulls per the dropdown.")
        col.label(text="Output blank = next to .blend / Desktop.")


classes = (AF_Props, AF_OT_export, AF_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.afterframe = bpy.props.PointerProperty(type=AF_Props)


def unregister():
    del bpy.types.WindowManager.afterframe
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
