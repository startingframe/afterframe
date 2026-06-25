"""
jsx_writer.py — build the self-contained After Effects .jsx. PURE (no bpy).

The DUMB side: all coordinate/lens/animation math is done in Python; the .jsx only reads pre-computed
values and builds the comp + camera + nulls. Payload schema (see exporter.build_payload):
  comp: {name,width,height,pixelAspect,fps,duration}
  worldNull: {position:[x,y,z]}
  camera: {name, position:[[t,[x,y,z]]...], orientation:[[t,[x,y,z]]...], zoom:[[t,val]...]}
  nulls: [{name, position:[[t,[x,y,z]]...], orientation:[[t,[x,y,z]]...]}]
"""

import json

JSX_TEMPLATE = r"""// Afterframe — Blender -> After Effects. Auto-generated; do not hand-edit.
// Run in AE:  File > Scripts > Run Script File...  -> select this .jsx
var DATA = __DATA__;
(function () {
    app.beginUndoGroup("Afterframe Import");
    var c = DATA.comp;
    var comp = app.project.items.addComp(c.name, c.width, c.height, c.pixelAspect, c.duration, c.fps);
    comp.openInViewer();

    var world = comp.layers.addNull(c.duration);
    world.threeDLayer = true;
    world.name = "BLENDER_WORLD";
    world.property("Transform").property("Position").setValue(DATA.worldNull.position);

    function keyVals(prop, frames) {
        for (var i = 0; i < frames.length; i++) prop.setValueAtTime(frames[i][0], frames[i][1]);
    }
    function applyChannel(prop, frames) {
        if (frames.length === 1) prop.setValue(frames[0][1]);
        else keyVals(prop, frames);
    }

    var cd = DATA.camera;
    var cam = comp.layers.addCamera(cd.name, [c.width / 2, c.height / 2]);
    cam.autoOrient = AutoOrientType.NO_AUTO_ORIENT;
    cam.parent = world;
    applyChannel(cam.property("Transform").property("Position"), cd.position);
    applyChannel(cam.property("Transform").property("Orientation"), cd.orientation);
    applyChannel(cam.property("Camera Options").property("Zoom"), cd.zoom);

    for (var n = 0; n < DATA.nulls.length; n++) {
        var nd = DATA.nulls[n];
        var nl = comp.layers.addNull(c.duration);
        nl.threeDLayer = true;
        nl.name = nd.name;
        nl.parent = world;
        applyChannel(nl.property("Transform").property("Position"), nd.position);
        if (nd.orientation) applyChannel(nl.property("Transform").property("Orientation"), nd.orientation);
    }
    app.endUndoGroup();
})();
"""


def write_jsx(filepath, payload):
    """Write the self-contained .jsx for `payload` to `filepath`. Returns the path."""
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(JSX_TEMPLATE.replace("__DATA__", json.dumps(payload)))
    return filepath
