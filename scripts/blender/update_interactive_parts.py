import os
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


def make_pbr_material(name, base_color, metallic=0.0, roughness=0.4, coat=0.0, coat_rough=0.05):
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


def create_or_get_empty(name, world_pos, parent):
    emp = bpy.data.objects.get(name)
    if emp is None:
        emp = bpy.data.objects.new(name, None)
        emp.empty_display_type = "PLAIN_AXES"
        emp.empty_display_size = 0.08
        bpy.context.scene.collection.objects.link(emp)
    emp.parent = parent
    bpy.context.view_layer.update()
    parent_world = parent.matrix_world.translation if parent else Vector((0.0, 0.0, 0.0))
    emp.location = Vector(world_pos) - parent_world
    emp.rotation_euler = (0.0, 0.0, 0.0)
    emp.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    return emp


def reparent_keep_world(obj, new_parent):
    """Move mesh object to new_parent without changing its world-space geometry."""
    bpy.context.view_layer.update()
    if obj.type == "MESH":
        mw = obj.matrix_world.copy()
        inv_parent = new_parent.matrix_world.inverted()
        local_mat = inv_parent @ mw
        obj.parent = new_parent
        obj.matrix_basis = Matrix.Identity(4)
        obj.data.transform(local_mat)
        obj.data.update()
    else:
        mw = obj.matrix_world.copy()
        obj.parent = new_parent
        obj.matrix_world = mw
    bpy.context.view_layer.update()


def repivot_empty_keep_children(empty_obj, new_world_pos):
    """Move empty_obj to new_world_pos without shifting its mesh children in world space."""
    bpy.context.view_layer.update()
    children = list(empty_obj.children)
    old_world_locs = [c.matrix_world.copy() for c in children]
    parent_world = empty_obj.parent.matrix_world.translation if empty_obj.parent else Vector((0.0, 0.0, 0.0))
    empty_obj.location = Vector(new_world_pos) - parent_world
    bpy.context.view_layer.update()
    inv_empty = empty_obj.matrix_world.inverted()
    for c, mw in zip(children, old_world_locs):
        if c.type == "MESH":
            local_mat = inv_empty @ mw
            c.matrix_basis = Matrix.Identity(4)
            c.data.transform(local_mat)
            c.data.update()
    bpy.context.view_layer.update()


def separate_mesh_by_loose_parts(obj):
    """Separate mesh into loose islands preserving materials, UVs, and parent."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    verts = set(bm.verts)
    components = []
    while verts:
        start = next(iter(verts))
        stack = [start]
        comp_verts = {start}
        verts.remove(start)
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                ov = e.other_vert(v)
                if ov in verts:
                    verts.remove(ov)
                    comp_verts.add(ov)
                    stack.append(ov)
        components.append(comp_verts)

    if len(components) <= 1:
        bm.free()
        return [obj]

    results = []
    orig_mats = list(obj.data.materials)
    col = obj.users_collection[0] if obj.users_collection else bpy.context.scene.collection
    parent = obj.parent
    loc = obj.location.copy()

    for idx, comp_verts in enumerate(components):
        sub_bm = bmesh.new()
        vert_map = {v: sub_bm.verts.new(v.co) for v in comp_verts}
        sub_bm.verts.ensure_lookup_table()
        uv_src = bm.loops.layers.uv.active
        uv_dst = sub_bm.loops.layers.uv.new(uv_src.name) if uv_src else None
        seen = set()
        for v in comp_verts:
            for f in v.link_faces:
                if f in seen:
                    continue
                seen.add(f)
                if all(fv in vert_map for fv in f.verts):
                    try:
                        nf = sub_bm.faces.new([vert_map[fv] for fv in f.verts])
                        nf.material_index = f.material_index
                        nf.smooth = f.smooth
                        if uv_src and uv_dst:
                            for ls, ld in zip(f.loops, nf.loops):
                                ld[uv_dst].uv = ls[uv_src].uv
                    except ValueError:
                        pass
        nm = bpy.data.meshes.new(f"{obj.name}_sub{idx}")
        sub_bm.to_mesh(nm)
        sub_bm.free()
        for m in orig_mats:
            nm.materials.append(m)
        no = bpy.data.objects.new(f"{obj.name}_sub{idx}", nm)
        col.objects.link(no)
        no.parent = parent
        no.location = loc
        results.append(no)

    bm.free()
    bpy.data.objects.remove(obj, do_unlink=True)
    return results


def world_bounds(obj):
    bpy.context.view_layer.update()
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def add_box(bm, center, size, mat_index=0, rot_x=0.0):
    sx, sy, sz = size
    mat = Matrix.Translation(center) @ Matrix.Rotation(rot_x, 4, "X") @ Matrix.Diagonal((sx, sy, sz, 1.0))
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=mat)
    for v in ret["verts"]:
        for f in v.link_faces:
            f.material_index = mat_index


def run():
    if "Lotus_Exige_S2" not in bpy.data.objects:
        bpy.ops.wm.open_mainfile(filepath=r"c:\Projekte\LOTUS EXIGE S2\blender_work\lotus_exige_s2.blend")

    # Reset any open rotation if rerun
    for ename in ("Tuer_Links", "Tuer_Rechts", "Klappe_Motor_Kofferraum", "Klappe_Service_Vorne", "Dach_Hardtop"):
        eo = bpy.data.objects.get(ename)
        if eo:
            eo.rotation_euler = (0.0, 0.0, 0.0)

    # 1. Re-pivot Doors to true front hinge positions
    tuer_l = bpy.data.objects["Tuer_Links"]
    tuer_r = bpy.data.objects["Tuer_Rechts"]
    repivot_empty_keep_children(tuer_l, (0.74, -0.54, 0.54))
    repivot_empty_keep_children(tuer_r, (-0.74, -0.54, 0.54))

    # 2. Rear Engine & Trunk Decklid (Klappe_Motor_Kofferraum)
    grp_heck = bpy.data.objects["GRP_Karosserie_HeckClam"]
    klappe_heck = create_or_get_empty("Klappe_Motor_Kofferraum", (0.0, 0.585, 1.115), grp_heck)
    for name in ("Object_503", "Object_506", "Object_509", "Object_383", "Object_387"):
        o = bpy.data.objects.get(name)
        if o:
            reparent_keep_world(o, klappe_heck)

    # Remove opaque placeholder engine-bay cover plates so engine + trunk are clearly visible when lid opens
    for blocker in ("Object_367", "Object_346_part21", "Object_346_part22", "Object_349", "Object_352"):
        o = bpy.data.objects.get(blocker)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)

    # Build rear trunk compartment (Kofferraum_Wanne) inside GRP_Chassis right behind engine/silencer
    if "Kofferraum_Wanne" not in bpy.data.objects:
        mat_carpet = make_pbr_material("MAT_Trunk_Carpet", (0.045, 0.048, 0.054), metallic=0.0, roughness=0.92)
        mat_alu = bpy.data.materials["MAT_Chassis_Alu"]
        bm_tr = bmesh.new()
        # Open-top trunk tub behind engine/subframe (Y=1.34..1.68, X=-0.38..0.38, Z=0.38..0.68)
        add_box(bm_tr, (0.0, 1.51, 0.39), (0.76, 0.34, 0.02), 0)  # bottom
        add_box(bm_tr, (0.0, 1.35, 0.54), (0.76, 0.02, 0.30), 0)  # front firewall
        add_box(bm_tr, (0.0, 1.67, 0.54), (0.76, 0.02, 0.30), 0)  # rear wall
        add_box(bm_tr, (-0.37, 1.51, 0.54), (0.02, 0.34, 0.30), 0)  # right wall
        add_box(bm_tr, (0.37, 1.51, 0.54), (0.02, 0.34, 0.30), 0)  # left wall
        add_box(bm_tr, (0.0, 1.51, 0.69), (0.78, 0.36, 0.015), 1)  # aluminum rim lip? No: leave top open, frame edges!
        # Replace top rim with 4 perimeter lip strips so inside stays open!
        bm_tr.free()

        bm_tr = bmesh.new()
        add_box(bm_tr, (0.0, 1.51, 0.39), (0.76, 0.34, 0.02), 0)
        add_box(bm_tr, (0.0, 1.35, 0.54), (0.76, 0.02, 0.30), 0)
        add_box(bm_tr, (0.0, 1.67, 0.54), (0.76, 0.02, 0.30), 0)
        add_box(bm_tr, (-0.37, 1.51, 0.54), (0.02, 0.34, 0.30), 0)
        add_box(bm_tr, (0.37, 1.51, 0.54), (0.02, 0.34, 0.30), 0)
        # Perimeter aluminum seal flange
        add_box(bm_tr, (0.0, 1.35, 0.695), (0.78, 0.028, 0.012), 1)
        add_box(bm_tr, (0.0, 1.67, 0.695), (0.78, 0.028, 0.012), 1)
        add_box(bm_tr, (-0.37, 1.51, 0.695), (0.028, 0.34, 0.012), 1)
        add_box(bm_tr, (0.37, 1.51, 0.695), (0.028, 0.34, 0.012), 1)
        m_tr = bpy.data.meshes.new("Kofferraum_Wanne")
        bm_tr.to_mesh(m_tr)
        bm_tr.free()
        m_tr.materials.append(mat_carpet)
        m_tr.materials.append(mat_alu)
        o_tr = bpy.data.objects.new("Kofferraum_Wanne", m_tr)
        bpy.context.scene.collection.objects.link(o_tr)
        o_tr.parent = bpy.data.objects["GRP_Chassis"]

    # 3. Front Service Flaps (Klappe_Service_Vorne) under GRP_Karosserie_FrontClam
    grp_front = bpy.data.objects["GRP_Karosserie_FrontClam"]
    klappe_front = create_or_get_empty("Klappe_Service_Vorne", (0.0, -0.56, 0.735), grp_front)
    for src_name in ("Object_462", "Object_474"):
        so = bpy.data.objects.get(src_name)
        if not so:
            continue
        parts = separate_mesh_by_loose_parts(so)
        for p in parts:
            xmin, xmax, ymin, ymax, zmin, zmax = world_bounds(p)
            # Front service access panels sit between X=[-0.67,0.67], Y=[-1.28,-0.53], Z=[0.62,0.76]
            if ymin > -1.30 and ymax < -0.52 and zmin > 0.60 and zmax < 0.77 and xmin > -0.68 and xmax < 0.68:
                reparent_keep_world(p, klappe_front)

    # Add aluminum radiator assembly in GRP_Chassis visible beneath front service flaps
    if "Chassis_Front_Radiator" not in bpy.data.objects:
        mat_alu = bpy.data.materials["MAT_Chassis_Alu"]
        mat_dark = bpy.data.materials["MAT_Engine_Dark"]
        bm_rad = bmesh.new()
        add_box(bm_rad, (0.0, -0.96, 0.49), (0.68, 0.34, 0.045), 0, rot_x=0.35)
        for ri in range(11):
            rx = -0.30 + ri * 0.06
            add_box(bm_rad, (rx, -0.96, 0.505), (0.012, 0.32, 0.03), 1, rot_x=0.35)
        # Dual cooling fan shrouds underneath
        add_box(bm_rad, (-0.17, -0.94, 0.46), (0.26, 0.24, 0.025), 1, rot_x=0.35)
        add_box(bm_rad, (0.17, -0.94, 0.46), (0.26, 0.24, 0.025), 1, rot_x=0.35)
        m_rad = bpy.data.meshes.new("Chassis_Front_Radiator")
        bm_rad.to_mesh(m_rad)
        bm_rad.free()
        m_rad.materials.append(mat_alu)
        m_rad.materials.append(mat_dark)
        o_rad = bpy.data.objects.new("Chassis_Front_Radiator", m_rad)
        bpy.context.scene.collection.objects.link(o_rad)
        o_rad.parent = bpy.data.objects["GRP_Chassis"]

    # 4. Removable Hardtop Roof (Dach_Hardtop) under GRP_Karosserie_Dach
    grp_dach = bpy.data.objects["GRP_Karosserie_Dach"]
    dach_hardtop = create_or_get_empty("Dach_Hardtop", (0.0, 0.16, 1.09), grp_dach)
    roof_panel_names = {
        "Object_346_part13", "Object_346_part14", "Object_346_part15",
        "Object_361_part13", "Object_364_part3",
        "Object_343_part0", "Object_343_part2", "Object_343_part4", "Object_343_part5", "Object_343_part6",
    }
    for name in roof_panel_names:
        o = bpy.data.objects.get(name)
        if o:
            reparent_keep_world(o, dach_hardtop)

    # Purge unused orphan data blocks
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    bpy.context.view_layer.update()
    print("Interactive assemblies updated successfully!")
    for ename in ("Tuer_Links", "Tuer_Rechts", "Klappe_Motor_Kofferraum", "Klappe_Service_Vorne", "Dach_Hardtop"):
        eo = bpy.data.objects[ename]
        print(f" - {ename}: world_loc={tuple(round(x,3) for x in eo.matrix_world.translation)}, children={len(eo.children)}")


run()
