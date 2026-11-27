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


def make_pbr_material(name, base_color, metallic=0.0, roughness=0.4, coat=0.0, coat_rough=0.08):
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
    return mat


def add_beveled_box(bm, center, size, bevel_width=0.008, mat_index=0):
    sx, sy, sz = size
    mat = Matrix.Translation(center) @ Matrix.Diagonal((sx, sy, sz, 1.0))
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=mat)
    verts = ret["verts"]
    edges = list({e for v in verts for e in v.link_edges})
    faces = list({f for v in verts for f in v.link_faces})
    for f in faces:
        f.material_index = mat_index
        f.smooth = True
    if bevel_width > 0:
        b_ret = bmesh.ops.bevel(
            bm,
            geom=edges,
            offset=bevel_width,
            segments=2,
            affect="EDGES",
            clamp_overlap=True,
        )
        for f in b_ret.get("faces", []):
            f.material_index = mat_index
            f.smooth = True


def add_cylinder(bm, center, r1, r2, depth, segments=22, axis="Z", mat_index=0):
    mat = Matrix.Translation(center)
    if axis == "X":
        mat = mat @ Matrix.Rotation(math.pi / 2, 4, "Y")
    elif axis == "Y":
        mat = mat @ Matrix.Rotation(math.pi / 2, 4, "X")
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


def add_tube(bm, p1, p2, radius, segments=14, mat_index=0):
    v1, v2 = Vector(p1), Vector(p2)
    diff = v2 - v1
    if diff.length < 1e-5:
        return
    mid = (v1 + v2) * 0.5
    quat = diff.normalized().to_track_quat("Z", "Y")
    mat = Matrix.Translation(mid) @ quat.to_matrix().to_4x4()
    ret = bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius,
        radius2=radius,
        depth=diff.length,
        matrix=mat,
    )
    for v in ret["verts"]:
        for f in v.link_faces:
            f.material_index = mat_index
            f.smooth = True


def add_curved_pipe(bm, points, radius, segments=12, mat_index=0):
    pts = [Vector(p) for p in points]
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            t = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = (pts[i + 1] - pts[i - 1]).normalized()
        up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        n1 = t.cross(up).normalized()
        n2 = t.cross(n1).normalized()
        ring = []
        for s in range(segments):
            a = 2.0 * math.pi * s / segments
            ring.append(bm.verts.new(p + (n1 * math.cos(a) + n2 * math.sin(a)) * radius))
        rings.append(ring)

    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        for s in range(segments):
            sn = (s + 1) % segments
            f = bm.faces.new((r0[s], r0[sn], r1[sn], r1[s]))
            f.material_index = mat_index
            f.smooth = True
    f0 = bm.faces.new(list(reversed(rings[0])))
    f0.material_index = mat_index
    f1 = bm.faces.new(rings[-1])
    f1.material_index = mat_index


def run():
    if "Lotus_Exige_S2" not in bpy.data.objects:
        bpy.ops.wm.open_mainfile(filepath=r"c:\Projekte\LOTUS EXIGE S2\blender_work\lotus_exige_s2.blend")

    grp_motor = bpy.data.objects["GRP_Motor_Antrieb"]
    grp_chassis = bpy.data.objects["GRP_Chassis"]
    bpy.context.view_layer.update()

    for old_name in ("Engine_2ZZ_GE_Supercharged", "Engine_Toyota_ZZ_Scan", "Engine_Toyota_ZZ_Block", "Engine_2ZZ_Supercharger_Kit", "Kofferraum_Wanne"):
        oo = bpy.data.objects.get(old_name)
        if oo:
            bpy.data.objects.remove(oo, do_unlink=True)

    mat_eng_alu = make_pbr_material("MAT_Engine_Alu", (0.52, 0.55, 0.59), metallic=0.86, roughness=0.35)
    mat_eng_dark = make_pbr_material("MAT_Engine_Dark", (0.035, 0.038, 0.045), metallic=0.25, roughness=0.48)
    mat_eng_red = make_pbr_material("MAT_Engine_Red", (0.62, 0.035, 0.045), metallic=0.32, roughness=0.28, coat=0.45)
    mat_exhaust = make_pbr_material("MAT_Exhaust", (0.60, 0.51, 0.41), metallic=0.93, roughness=0.22)
    mat_alu = bpy.data.materials["MAT_Chassis_Alu"]
    mat_silicone = make_pbr_material("MAT_Silicone_Blue", (0.04, 0.16, 0.45), metallic=0.05, roughness=0.36)

    eng_root = bpy.data.objects.get("toyota_1zz-fe_engine_209")
    if eng_root:
        keep_prefixes = (
            "block",
            "cylinder_head",
            "head_cover",
            "head_cover_gasket",
            "head_gasket",
            "ignition_coil",
            "exhaust_manifold",
            "oil_pan",
            "oil_filter",
            "oil_filler_cap",
            "timing_cover",
            "water_pump",
            "crank_pulley",
            "oil_pump",
            "crank_position_sensor",
        )
        kept_meshes = []
        removed_meshes = []

        bpy.context.view_layer.update()
        for ch in list(eng_root.children):
            is_kept = ch.name.startswith(keep_prefixes)
            meshes = [m for m in ch.children_recursive if m.type == "MESH"]
            if is_kept:
                for m in meshes:
                    kept_meshes.append((ch.name, m, m.matrix_world.copy()))
            else:
                removed_meshes.extend(meshes)

        for rm in removed_meshes:
            bpy.data.objects.remove(rm, do_unlink=True)

        # Unparent kept meshes before deleting wrapper empties
        for _, m_obj, _ in kept_meshes:
            m_obj.parent = None
            m_obj.matrix_basis = Matrix.Identity(4)

        for wrap_name in ("Sketchfab_model", "root", "GLTF_SceneRootNode", "toyota_1zz-fe_engine_209"):
            wo = bpy.data.objects.get(wrap_name)
            if wo:
                for c in list(wo.children_recursive):
                    if c.type == "EMPTY":
                        bpy.data.objects.remove(c, do_unlink=True)
                if wo.name in bpy.data.objects and wo.type == "EMPTY":
                    bpy.data.objects.remove(wo, do_unlink=True)

        inv_motor = grp_motor.matrix_world.inverted()
        scale_mat = Matrix.Diagonal((0.90, 0.90, 0.90, 1.0))
        rot_mat = Matrix.Rotation(math.pi, 4, "Z")
        place_world = Matrix.Translation((-0.06, 1.00, 0.215)) @ rot_mat @ scale_mat

        total_kept_faces = 0
        for part_name, m_obj, mw in kept_meshes:
            m_obj.parent = grp_motor
            m_obj.matrix_basis = Matrix.Identity(4)
            m_obj.data.transform(inv_motor @ place_world @ mw)
            m_obj.data.update()

            fcount = len(m_obj.data.polygons)
            if fcount > 8000:
                mod = m_obj.modifiers.new(name="Decimate", type="DECIMATE")
                mod.ratio = 0.35
                bpy.context.view_layer.objects.active = m_obj
                bpy.ops.object.modifier_apply(modifier=mod.name)

            m_obj.data.materials.clear()
            if part_name.startswith("head_cover."):
                m_obj.data.materials.append(mat_eng_red)
            elif part_name.startswith(("ignition_coil", "oil_pan", "oil_filter", "oil_filler_cap", "crank_pulley", "head_cover_gasket", "head_gasket")):
                m_obj.data.materials.append(mat_eng_dark)
            elif part_name.startswith("exhaust_manifold"):
                m_obj.data.materials.append(mat_exhaust)
            else:
                m_obj.data.materials.append(mat_eng_alu)

            for p in m_obj.data.polygons:
                p.use_smooth = True
            total_kept_faces += len(m_obj.data.polygons)

        print(f"Mounted Toyota ZZ CAD Engine ({len(kept_meshes)} meshes, {total_kept_faces} faces total)")

    bm = bmesh.new()
    add_cylinder(bm, (0.18, 1.00, 0.42), 0.140, 0.115, 0.15, 22, "X", 0)
    add_cylinder(bm, (0.31, 1.00, 0.42), 0.110, 0.088, 0.14, 20, "X", 0)
    add_beveled_box(bm, (0.24, 1.14, 0.35), (0.18, 0.14, 0.13), 0.012, 0)
    for xi in range(5):
        add_beveled_box(bm, (0.20 + xi * 0.035, 1.00, 0.525), (0.01, 0.13, 0.016), 0.002, 0)
    add_cylinder(bm, (0.35, 1.17, 0.34), 0.036, 0.024, 0.06, 16, "X", 1)
    add_cylinder(bm, (0.08, 1.17, 0.34), 0.036, 0.024, 0.06, 16, "X", 1)
    add_tube(bm, (0.34, 1.17, 0.34), (0.64, 1.20, 0.318), 0.017, 12, 1)
    add_tube(bm, (0.09, 1.17, 0.34), (-0.64, 1.20, 0.318), 0.017, 12, 1)

    add_cylinder(bm, (-0.06, 0.81, 0.56), 0.068, 0.068, 0.25, 22, "X", 4)
    for ri in range(6):
        add_cylinder(bm, (-0.16 + ri * 0.04, 0.81, 0.56), 0.073, 0.073, 0.011, 22, "X", 0)
    add_cylinder(bm, (-0.23, 0.81, 0.56), 0.042, 0.025, 0.11, 18, "X", 0)
    add_cylinder(bm, (-0.295, 0.81, 0.56), 0.036, 0.036, 0.024, 20, "X", 2)
    add_cylinder(bm, (-0.285, 0.90, 0.47), 0.024, 0.024, 0.022, 16, "X", 1)
    add_tube(bm, (-0.292, 0.81, 0.59), (-0.28, 1.00, 0.41), 0.008, 8, 1)
    add_tube(bm, (-0.292, 0.81, 0.53), (-0.285, 0.90, 0.45), 0.008, 8, 1)
    add_tube(bm, (-0.285, 0.90, 0.45), (-0.28, 1.00, 0.33), 0.008, 8, 1)

    add_beveled_box(bm, (-0.05, 0.94, 0.80), (0.33, 0.20, 0.065), 0.010, 4)
    for fi in range(11):
        add_beveled_box(bm, (-0.19 + fi * 0.028, 0.94, 0.836), (0.008, 0.17, 0.012), 0.002, 1)
    add_beveled_box(bm, (-0.05, 1.00, 0.839), (0.17, 0.038, 0.010), 0.003, 2)
    add_curved_pipe(bm, [(-0.06, 0.81, 0.62), (-0.06, 0.77, 0.74), (-0.06, 0.84, 0.79)], 0.034, 16, 4)
    add_cylinder(bm, (-0.06, 0.79, 0.74), 0.039, 0.039, 0.040, 16, "Z", 5)
    for ci in range(4):
        rx = -0.18 + ci * 0.08
        add_curved_pipe(bm, [(rx, 0.92, 0.78), (rx, 0.87, 0.72), (rx, 0.91, 0.65)], 0.019, 12, 4)

    add_curved_pipe(bm, [(-0.04, 1.18, 0.38), (-0.02, 1.32, 0.32), (0.0, 1.44, 0.26), (0.0, 1.55, 0.24)], 0.032, 14, 3)
    add_cylinder(bm, (0.0, 1.44, 0.265), 0.052, 0.052, 0.14, 16, "Y", 3)
    add_cylinder(bm, (0.0, 1.56, 0.24), 0.075, 0.075, 0.46, 20, "X", 3)
    for tx in (-0.038, 0.038):
        add_tube(bm, (tx, 1.58, 0.235), (tx, 1.75, 0.225), 0.025, 16, 4)

    kit_mesh = bpy.data.meshes.new("Engine_2ZZ_Supercharger_Kit")
    bm.to_mesh(kit_mesh)
    bm.free()
    for m in (mat_eng_alu, mat_eng_dark, mat_eng_red, mat_exhaust, mat_alu, mat_silicone):
        kit_mesh.materials.append(m)
    kit_obj = bpy.data.objects.new("Engine_2ZZ_Supercharger_Kit", kit_mesh)
    bpy.context.scene.collection.objects.link(kit_obj)
    kit_obj.data.transform(grp_motor.matrix_world.inverted())
    kit_obj.data.update()
    kit_obj.parent = grp_motor

    mat_carpet = bpy.data.materials.get("MAT_Trunk_Carpet") or make_pbr_material("MAT_Trunk_Carpet", (0.045, 0.048, 0.054), metallic=0.0, roughness=0.92)
    bm_tr = bmesh.new()
    add_beveled_box(bm_tr, (0.0, 1.57, 0.425), (0.68, 0.26, 0.018), 0.003, 0)
    add_beveled_box(bm_tr, (0.0, 1.445, 0.55), (0.68, 0.018, 0.26), 0.003, 0)
    add_beveled_box(bm_tr, (0.0, 1.695, 0.55), (0.68, 0.018, 0.26), 0.003, 0)
    add_beveled_box(bm_tr, (-0.335, 1.57, 0.55), (0.018, 0.26, 0.26), 0.003, 0)
    add_beveled_box(bm_tr, (0.335, 1.57, 0.55), (0.018, 0.26, 0.26), 0.003, 0)
    add_beveled_box(bm_tr, (0.0, 1.445, 0.682), (0.70, 0.024, 0.010), 0.002, 1)
    add_beveled_box(bm_tr, (0.0, 1.695, 0.682), (0.70, 0.024, 0.010), 0.002, 1)
    add_beveled_box(bm_tr, (-0.335, 1.57, 0.682), (0.024, 0.26, 0.010), 0.002, 1)
    add_beveled_box(bm_tr, (0.335, 1.57, 0.682), (0.024, 0.26, 0.010), 0.002, 1)

    m_tr = bpy.data.meshes.new("Kofferraum_Wanne")
    bm_tr.to_mesh(m_tr)
    bm_tr.free()
    m_tr.materials.append(mat_carpet)
    m_tr.materials.append(mat_alu)
    o_tr = bpy.data.objects.new("Kofferraum_Wanne", m_tr)
    bpy.context.scene.collection.objects.link(o_tr)
    o_tr.parent = grp_chassis

    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    bpy.context.view_layer.update()
    print("Upgraded Toyota ZZ CAD Engine + Supercharger Kit + Trunk Tub complete!")


run()
