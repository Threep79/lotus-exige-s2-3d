import os
import math
import bpy
import bmesh
from mathutils import Vector, Matrix


def get_bsdf(mat):
    if not mat or not mat.use_nodes:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def set_bsdf_input(bsdf, name, value):
    if bsdf and name in bsdf.inputs:
        bsdf.inputs[name].default_value = value


def make_pbr_material(name, base_color, metallic=0.0, roughness=0.45, coat=0.0, coat_rough=0.08, alpha=1.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    set_bsdf_input(bsdf, "Base Color", (*base_color[:3], 1.0))
    set_bsdf_input(bsdf, "Metallic", metallic)
    set_bsdf_input(bsdf, "Roughness", roughness)
    set_bsdf_input(bsdf, "Coat Weight", coat)
    set_bsdf_input(bsdf, "Coat Roughness", coat_rough)
    set_bsdf_input(bsdf, "Alpha", alpha)
    if alpha < 1.0 and hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    return mat


def add_box(bm, center, size, mat_index=0):
    sx, sy, sz = size
    mat = Matrix.Translation(center) @ Matrix.Diagonal((sx, sy, sz, 1.0))
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=mat)
    for v in ret["verts"]:
        for f in v.link_faces:
            f.material_index = mat_index


def add_cylinder(bm, center, r1, r2, depth, segments=20, mat_index=0):
    mat = Matrix.Translation(center)
    ret = bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=r1,
        radius2=r2,
        depth=depth,
        matrix=mat,
    )
    for v in ret["verts"]:
        for f in v.link_faces:
            f.material_index = mat_index
            f.smooth = True


def add_pleated_shift_boot(bm, center_xy, z_bottom, z_top, rx_bot, ry_bot, r_top, mat_index=1):
    """Build a sculpted pleated leather shift boot from oval bezel up to shift collar."""
    cx, cy = center_xy
    rings_spec = [
        (0.00, rx_bot, ry_bot),
        (0.20, rx_bot * 0.78, ry_bot * 0.78),
        (0.34, rx_bot * 0.66, ry_bot * 0.66),
        (0.50, rx_bot * 0.56, ry_bot * 0.54),
        (0.66, rx_bot * 0.44, ry_bot * 0.42),
        (0.82, rx_bot * 0.34, ry_bot * 0.32),
        (1.00, r_top, r_top),
    ]
    segs = 24
    rings = []
    for t, rx, ry in rings_spec:
        z = z_bottom + (z_top - z_bottom) * t
        ring = []
        for s in range(segs):
            a = 2.0 * math.pi * s / segs
            ring.append(bm.verts.new((cx + math.cos(a) * rx, cy + math.sin(a) * ry, z)))
        rings.append(ring)

    for i in range(len(rings) - 1):
        r0 = rings[i]
        r1 = rings[i + 1]
        for s in range(segs):
            sn = (s + 1) % segs
            f = bm.faces.new((r0[s], r0[sn], r1[sn], r1[s]))
            f.material_index = mat_index
            f.smooth = True

    # Cap top & bottom
    f_bot = bm.faces.new(list(reversed(rings[0])))
    f_bot.material_index = mat_index
    f_top = bm.faces.new(rings[-1])
    f_top.material_index = mat_index


def run():
    if "Lotus_Exige_S2" not in bpy.data.objects:
        bpy.ops.wm.open_mainfile(filepath=r"c:\Projekte\LOTUS EXIGE S2\blender_work\lotus_exige_s2.blend")

    grp_int = bpy.data.objects["GRP_Interieur"]
    bpy.context.view_layer.update()

    # 1. Remove broken skinned shift boot (Object_213) and old Interior_Center_Console
    for old_name in ("Object_213", "Interior_Center_Console", "Interior_Shifter_And_Console"):
        oo = bpy.data.objects.get(old_name)
        if oo:
            bpy.data.objects.remove(oo, do_unlink=True)

    # 2. Align & seat aluminum gear knob (Object_219) firmly onto shifter rod
    knob = bpy.data.objects.get("Object_219")
    if knob:
        pts = [knob.matrix_world @ Vector(c) for c in knob.bound_box]
        kx = sum(p.x for p in pts) / len(pts)
        ky = sum(p.y for p in pts) / len(pts)
        kz_min = min(p.z for p in pts)
        # Center over oval bezel (0.0, -0.281), bottom of knob at Z = 0.452
        shift_w = Vector((0.0 - kx, -0.281 - ky, 0.452 - kz_min))
        knob.data.transform(Matrix.Translation(shift_w))
        knob.data.update()

    # 3. Build solid Interior_Shifter_And_Console (full floor seal + dark shifter well + pleated boot + steel rod)
    mat_console = make_pbr_material("MAT_Interior_Console", (0.022, 0.025, 0.030), metallic=0.04, roughness=0.52)
    mat_boot = make_pbr_material("MAT_Shifter_Boot", (0.017, 0.019, 0.024), metallic=0.0, roughness=0.56)
    mat_rod = make_pbr_material("MAT_Interior_Trim_Alu", (0.58, 0.61, 0.65), metallic=0.92, roughness=0.22)

    bm = bmesh.new()
    # Solid center tunnel base sealing cleanly from floorpan (Z=0.145) up into outer console shell (Z=0.315)
    add_box(bm, (0.0, -0.14, 0.230), (0.124, 0.72, 0.170), 0)
    # Rear console extension tucked slightly lower so seatbelt hardware stays unobstructed
    add_box(bm, (0.0, 0.22, 0.215), (0.116, 0.20, 0.140), 0)
    # Dark recessed shifter well directly underneath the oval bezel (Object_236)
    add_box(bm, (0.0, -0.281, 0.340), (0.112, 0.142, 0.070), 0)
    # Sculpted pleated leather shift boot rising from bezel (Z=0.365) up to collar (Z=0.448)
    add_pleated_shift_boot(
        bm,
        center_xy=(0.0, -0.281),
        z_bottom=0.365,
        z_top=0.448,
        rx_bot=0.048,
        ry_bot=0.060,
        r_top=0.015,
        mat_index=1,
    )
    # Solid brushed steel shift rod + collar connecting boot to knob bottom (Z=0.44..0.485)
    add_cylinder(bm, (0.0, -0.281, 0.452), 0.014, 0.012, 0.018, segments=20, mat_index=2)
    add_cylinder(bm, (0.0, -0.281, 0.465), 0.009, 0.009, 0.045, segments=16, mat_index=2)

    mesh = bpy.data.meshes.new("Interior_Shifter_And_Console")
    bm.to_mesh(mesh)
    bm.free()
    for m in (mat_console, mat_boot, mat_rod):
        mesh.materials.append(m)
    obj = bpy.data.objects.new("Interior_Shifter_And_Console", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.transform(grp_int.matrix_world.inverted())
    obj.data.update()
    obj.parent = grp_int

    # 4. Fix Side Windows: remove duplicate coplanar inner panes & enforce single clean double-sided glass
    for dup_glass in ("Object_44", "Object_87"):
        dg = bpy.data.objects.get(dup_glass)
        if dg:
            bpy.data.objects.remove(dg, do_unlink=True)

    mat_side_glass = make_pbr_material(
        "MAT_Glass_Side",
        (0.04, 0.06, 0.08),
        metallic=0.0,
        roughness=0.04,
        coat=0.65,
        coat_rough=0.04,
        alpha=0.28,
    )
    mat_side_glass.use_backface_culling = False

    for outer_glass in ("Object_75", "Object_118"):
        og = bpy.data.objects.get(outer_glass)
        if og and og.type == "MESH":
            og.data.materials.clear()
            og.data.materials.append(mat_side_glass)

    for gmat_name in ("INT_Vetro", "CAR_lights_0"):
        gm = bpy.data.materials.get(gmat_name)
        if gm:
            gm.use_backface_culling = False

    # Purge unused blocks
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    bpy.context.view_layer.update()
    print("Shifter, console seal, and side window glass fixed cleanly!")


run()
