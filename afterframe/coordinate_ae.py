"""
coordinate_ae.py — Blender -> After Effects axis/rotation conversion. PURE MATH (no bpy).

The rotation-gate module for Afterframe. Unit-tested by test_ae_math.py (run it before trusting
anything here). This replaces v0's broken `ae_orientation` (guessed R_FIX/EULER_ORDER + lossy
`% 360`, no continuity — the "ZYX" bug). The method is BlendFusion's proven approach
(conjugation + a derived camera offset), re-derived for AE's coordinate system, plus continuity.

COORDINATE SYSTEMS
  Blender world: X right, Y forward (into scene), Z up. Right-handed. Camera looks down local -Z,
                 up = local +Y.
  After Effects: X right, Y DOWN, Z into screen. Right-handed (right x down = into-screen).
                 Camera looks down local +Z, up = local -Y. Degrees, pixels.

POSITION  — basis change C (Blender -> AE):  (x, y, z) -> (x, -z, y)   [ == R_x(+90) ]
  AE_X = B_X ;  AE_Y = -B_Z  (Z-up -> Y-down) ;  AE_Z = B_Y  (forward -> into screen).

ROTATION  — an orientation transforms by CONJUGATION:  R_ae = C · R_b · C^T   (NOT a component
  swap; a swap is only right for degenerate single-axis rotations — the exact trap BlendFusion hit).

CAMERA OFFSET  — after the conjugation the AE camera's local frame still differs from Blender's by
  a fixed local rotation. DERIVED (see test_ae_math.py, two independent cases):
    • A Blender cam at rx=+90 looks forward (into the scene) -> the AE cam must be at identity
      (looking +Z, into the screen). Conjugating R_x(90) by C=R_x(90) gives R_x(90), so the local
      offset must cancel it: R_x(-90).
    • A Blender identity cam looks -Z (down) -> the AE cam must look +Y (down); R_x(-90) does that.
  => CAMERA_X_OFFSET = -90, applied as a LOCAL post-multiply  R_ae = (C·R_b·C^T) · R_x(-90).
  Same value BlendFusion landed on. This is a PRINCIPLED DEFAULT — AE's Orientation sign/axis
  conventions can still flip it. The render-match overlay is the judge. Knobs if it's off:
    • mirrored / backwards  -> try CAMERA_X_OFFSET = +90, or switch the offset axis to 'Y'.
    • pan/roll swapped      -> change EULER_ORDER.

EULER ORDER  — AE composes Orientation in a fixed order (v0's claim: ZYX). The R_ae MATRIX is the
  ground truth; the order is only the *encoding* of that matrix into AE's three X/Y/Z numbers.
  Parameterized so the overlay can switch ZYX <-> XYZ <-> YXZ without touching the matrix math.

CONTINUITY  — euler decomposition is per-frame ambiguous (a ±360 wrap AND a flip branch). Each
  frame we pick the representation closest to the previous frame, so a pan crossing 0°/360° does
  NOT spin the long way between sparse keys. This is the real fix v0 lacked.
"""

import math

# --- calibration constants — ✅ VALIDATED & LOCKED 2026-06-25 by AE render-match overlay ---
# All 5 markers nested dead-center in their Blender backplate circles across base + yaw + pitch +
# roll + combined (AE 26.3). The derived defaults were correct on the FIRST real test — no flips.
# SCOPE: validated the gentle gate (±18° isolated axes, all nested) AND a full ROLL WRAP 0->390°
# (markers nested every 45° through the 360->0 wrap, no snap/reversal — confirms AE renders large
# orientation VALUES and honors the continuity ENCODING). Still NOT visually confirmed (covered by the
# closed-form tests incl. the gimbal branch; low real-world risk): near-gimbal / yaw|tilt past ~90°
# (those moves take the markers off-frame, so they can't be overlaid). And AE's interpolation across
# SPARSE keys is a v1-feature-time test — the current DENSE bake is unaffected by it.
CAMERA_X_OFFSET = -90.0      # degrees; local post-multiply about X. Derived two ways, confirmed.
CAMERA_OFFSET_AXIS = 'X'     # confirmed (no mirror).
EULER_ORDER = 'ZYX'          # confirmed (no axis swap).
ORIENT_SIGN = (1.0, 1.0, 1.0)  # confirmed — AE negated no channel (the det(-1) knob stayed identity).

# Basis change C = R_x(+90):  (x, y, z) -> (x, -z, y)
_C = ((1.0, 0.0, 0.0),
      (0.0, 0.0, -1.0),
      (0.0, 1.0, 0.0))

_EPS = 1e-7


# ------------------------------- tiny 3x3 linear algebra -------------------------------

def _matmul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )

def _transpose(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))

def _det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))

def _rx(r):
    c, s = math.cos(r), math.sin(r)
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))

def _ry(r):
    c, s = math.cos(r), math.sin(r)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))

def _rz(r):
    c, s = math.cos(r), math.sin(r)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))

_AX = {'X': _rx, 'Y': _ry, 'Z': _rz}


# ------------------------------- euler <-> matrix (any order) -------------------------------

def euler_to_matrix(x, y, z, order):
    """Per-axis angles (radians, about X/Y/Z) composed in `order` (order[0] applied FIRST).
    Matches the mathutils convention: 'XYZ' => Rz·Ry·Rx."""
    ang = {'X': x, 'Y': y, 'Z': z}
    m = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    for axis in reversed(order):        # order[0] first => its matrix sits rightmost
        m = _matmul(m, _AX[axis](ang[axis]))
    return m


def matrix_to_euler(m, order):
    """Decompose a rotation matrix into per-axis angles (x, y, z) radians such that
    euler_to_matrix(x, y, z, order) reconstructs `m`. Implemented for XYZ / ZYX / YXZ."""
    if order == 'XYZ':                  # m = Rz·Ry·Rx
        cy = math.sqrt(m[0][0] ** 2 + m[1][0] ** 2)
        if cy > _EPS:
            x = math.atan2(m[2][1], m[2][2])
            y = math.atan2(-m[2][0], cy)
            z = math.atan2(m[1][0], m[0][0])
        else:
            x = math.atan2(-m[1][2], m[1][1]); y = math.atan2(-m[2][0], cy); z = 0.0
        return (x, y, z)
    if order == 'ZYX':                  # m = Rx·Ry·Rz
        cy = math.sqrt(m[0][0] ** 2 + m[0][1] ** 2)
        if cy > _EPS:
            x = math.atan2(-m[1][2], m[2][2])
            y = math.atan2(m[0][2], cy)
            z = math.atan2(-m[0][1], m[0][0])
        else:
            x = 0.0; y = math.atan2(m[0][2], cy); z = math.atan2(m[1][0], m[1][1])
        return (x, y, z)
    if order == 'YXZ':                  # m = Rz·Rx·Ry
        cx = math.sqrt(m[2][1] ** 2 + m[2][2] ** 2)
        x = math.asin(max(-1.0, min(1.0, m[2][1])))
        if cx > _EPS:
            y = math.atan2(-m[2][0], m[2][2])
            z = math.atan2(-m[0][1], m[1][1])
        else:
            y = 0.0; z = math.atan2(m[0][1], m[0][0])
        return (x, y, z)
    raise ValueError("unsupported euler order: %r" % order)


# ------------------------------- public conversion -------------------------------

def blender_to_ae_position(x, y, z):
    """Blender (X, Y, Z) -> AE (X, Y, Z) = (x, -z, y). Add the comp-center world-null offset
    downstream (handled by the writer; this is the raw axis map)."""
    return (x, -z, y)


def ae_rotation_matrix(rx, ry, rz, is_camera):
    """Blender world euler (XYZ, radians) -> the AE-space rotation MATRIX.
    Object/null: R_ae = C·R_b·C^T.  Camera: also · R_offset(CAMERA_X_OFFSET)."""
    r_b = euler_to_matrix(rx, ry, rz, 'XYZ')        # Blender world euler is XYZ
    r_ae = _matmul(_matmul(_C, r_b), _transpose(_C))
    if is_camera:
        off = _AX[CAMERA_OFFSET_AXIS](math.radians(CAMERA_X_OFFSET))
        r_ae = _matmul(r_ae, off)
    return r_ae


def blender_to_ae_orientation(rx, ry, rz, is_camera=False, order=None):
    """Single-frame: Blender euler XYZ (radians) -> AE orientation (x, y, z) DEGREES."""
    order = order or EULER_ORDER
    e = matrix_to_euler(ae_rotation_matrix(rx, ry, rz, is_camera), order)
    return tuple(math.degrees(a) * s for a, s in zip(e, ORIENT_SIGN))


# ------------------------------- continuity (the ZYX fix) -------------------------------

def _unwrap(a, ref):
    """Shift a by multiples of 2π to be within ±π of ref."""
    while a - ref > math.pi:
        a -= 2.0 * math.pi
    while a - ref < -math.pi:
        a += 2.0 * math.pi
    return a

def _flip(e, order):
    """The other euler that yields the same rotation (Tait-Bryan, distinct axes): the order's
    MIDDLE axis takes (π − angle); the outer two take (angle + π). `e` is per-axis (x, y, z)."""
    mid = order[1]
    idx = {'X': 0, 'Y': 1, 'Z': 2}
    out = list(e)
    for ax, i in idx.items():
        out[i] = (math.pi - e[i]) if ax == mid else (e[i] + math.pi)
    return tuple(out)

def _continuous(m, order, prev):
    """Decompose m, choosing the representation (primary vs flip, each ±360-unwrapped) closest
    to prev (radians) — eliminates 359°->1° spins. prev=None for the first frame."""
    e = matrix_to_euler(m, order)
    if prev is None:
        return e
    best, best_d = None, float("inf")
    for cand in (e, _flip(e, order)):
        cu = tuple(_unwrap(cand[i], prev[i]) for i in range(3))
        d = sum((cu[i] - prev[i]) ** 2 for i in range(3))
        if d < best_d:
            best_d, best = d, cu
    return best


def bake_orientation_sequence(blender_eulers, is_camera=False, order=None):
    """A list of Blender world eulers (XYZ, radians) -> a list of AE orientations (x, y, z) DEGREES,
    continuity-unwrapped across the sequence. This is what the exporter feeds AE for animated cams."""
    order = order or EULER_ORDER
    out, prev = [], None
    for (rx, ry, rz) in blender_eulers:
        e = _continuous(ae_rotation_matrix(rx, ry, rz, is_camera), order, prev)
        prev = e
        out.append(tuple(math.degrees(a) * s for a, s in zip(e, ORIENT_SIGN)))
    return out


def bake_ae_matrix_sequence(ae_mats, order=None):
    """A list of ALREADY-IN-AE-SPACE 3x3 rotation matrices -> AE orientations (x, y, z) DEGREES,
    continuity-unwrapped. For transforms computed directly in AE space (e.g., a screen-replacement
    layer's seating frame) rather than via the Blender->AE conjugation."""
    order = order or EULER_ORDER
    out, prev = [], None
    for m in ae_mats:
        e = _continuous(m, order, prev)
        prev = e
        out.append(tuple(math.degrees(a) * s for a, s in zip(e, ORIENT_SIGN)))
    return out
