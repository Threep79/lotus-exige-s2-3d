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


def disconnect_socket_input(mat, bsdf, input_name):
    if not mat or not mat.use_nodes or not bsdf or input_name not in bsdf.inputs:
        return
    inp = bsdf.inputs[input_name]
    for link in list(inp.links):
        mat.node_tree.links.remove(link)


def make_pbr_material(name, base_color, metallic=0.0, roughness=0.45, coat=0.0, coat_rough=0.08):
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


def add_box(bm, center, size, mat_index=0, rot_x=0.0):
    sx, sy, sz = size
    mat = Matrix.Translation(center) @ Matrix.Rotation(rot_x, 4, "X") @ Matrix.Diagonal((sx, sy, sz, 1.0))
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=mat)
    for v in ret["verts"]:
        for f in v.link_faces:
            f.material_index = mat_index


def add_tube(bm, p1, p2, radius, segments=12, mat_index=0):
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


def split_faces_above_region(obj, target_parent, z_thresh=0.95, y_min=-0.24, y_max=0.56):
    """Move faces whose world centroid is inside the roof headliner/header zone into target_parent."""
    if not obj or obj.type != "MESH":
        return None
    bpy.context.view_layer.update()
    mw = obj.matrix_world.copy()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()

    roof_faces = []
    for f in bm.faces:
        wc = mw @ f.calc_center_median()
        if wc.z > z_thresh and y_min < wc.y < y_max:
            roof_faces.append(f)

    if not roof_faces:
        bm.free()
        return None

    # Create new mesh for extracted roof faces in target_parent local space
    inv_target = target_parent.matrix_world.inverted()
    to_target = inv_target @ mw

    sub_bm = bmesh.new()
    vmap = {}
    uv_src = bm.loops.layers.uv.active
    uv_dst = sub_bm.loops.layers.uv.new(uv_src.name) if uv_src else None

    for f in roof_faces:
        new_verts = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = sub_bm.verts.new(to_target @ v.co)
            new_verts.append(vmap[v])
        try:
            nf = sub_bm.faces.new(new_verts)
            nf.material_index = f.material_index
            nf.smooth = f.smooth
            if uv_src and uv_dst:
                for ls, ld in zip(f.loops, nf.loops):
                    ld[uv_dst].uv = ls[uv_src].uv
        except ValueError:
            pass

    # Delete extracted faces from source bmesh
    bmesh.ops.delete(bm, geom=roof_faces, context="FACES")
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()

    # Build new roof object
    new_mesh = bpy.data.meshes.new(f"{obj.name}_RoofTrim")
    sub_bm.to_mesh(new_mesh)
    sub_bm.free()
    for m in obj.data.materials:
        new_mesh.materials.append(m)

    new_obj = bpy.data.objects.new(f"{obj.name}_RoofTrim", new_mesh)
    bpy.context.scene.collection.objects.link(new_obj)
    new_obj.parent = target_parent
    return new_obj


def run():
    if "Lotus_Exige_S2" not in bpy.data.objects:
        bpy.ops.wm.open_mainfile(filepath=r"c:\Projekte\LOTUS EXIGE S2\blender_work\lotus_exige_s2.blend")

    grp_interieur = bpy.data.objects["GRP_Interieur"]
    grp_chassis = bpy.data.objects["GRP_Chassis"]
    dach_hardtop = bpy.data.objects["Dach_Hardtop"]
    bpy.context.view_layer.update()

    # 1. Mount imported Momo Steering Wheel (Sketchfab_model) into GRP_Interieur
    sw_root = bpy.data.objects.get("Sketchfab_model")
    if sw_root:
        # Remove OEM steering wheel objects
        for oem_name in ("Object_186", "Object_189", "Object_192", "Object_195", "Object_198"):
            oo = bpy.data.objects.get(oem_name)
            if oo:
                bpy.data.objects.remove(oo, do_unlink=True)

        def collect_sw(o, acc):
            if o.type == "MESH":
                acc.append(o)
            for c in o.children:
                collect_sw(c, acc)

        sw_meshes = []
        collect_sw(sw_root, sw_meshes)

        # Compute current center of Torus_Black knitted cotton_0 to center wheel at (0,0,0) first
        rim_obj = next((o for o in sw_meshes if "Torus_Black" in o.name), sw_meshes[0])
        pts = [rim_obj.matrix_world @ Vector(c) for c in rim_obj.bound_box]
        sw_cx = sum(p.x for p in pts) / len(pts)
        sw_cy = sum(p.y for p in pts) / len(pts)
        sw_cz = sum(p.z for p in pts) / len(pts)

        # Lotus steering wheel target world pos: (0.253, -0.220, 0.638)
        # Rotate slightly forward around X (-0.52 rad) so top leans forward toward dash (-Y)
        # and horn faces driver (+Y) cleanly at ~18 deg angle
        inv_int = grp_interieur.matrix_world.inverted()
        target_world = Vector((0.253, -0.220, 0.638))
        tilt_mat = Matrix.Rotation(math.pi, 4, "Z") @ Matrix.Rotation(0.16, 4, "X")
        place_mat = Matrix.Translation(target_world) @ tilt_mat @ Matrix.Translation((-sw_cx, -sw_cy, -sw_cz))

        for m_obj in sw_meshes:
            mw = m_obj.matrix_world.copy()
            local_mat = inv_int @ place_mat @ mw
            m_obj.parent = grp_interieur
            m_obj.matrix_basis = Matrix.Identity(4)
            m_obj.data.transform(local_mat)
            m_obj.data.update()
            # Light decimation on ultra-dense bolts/grip so GLB stays compact
            if len(m_obj.data.polygons) > 3000:
                mod = m_obj.modifiers.new(name="Decimate", type="DECIMATE")
                mod.ratio = 0.25 if "Circle.00" in m_obj.name else 0.5
                bpy.context.view_layer.objects.active = m_obj
                bpy.ops.object.modifier_apply(modifier=mod.name)

        # Clean Momo materials so grip is dark perforated Alcantara/leather, spokes satin black, logo crisp
        m_cotton = bpy.data.materials.get("Black_knitted_cotton")
        if m_cotton:
            bsdf = get_bsdf(m_cotton)
            disconnect_socket_input(m_cotton, bsdf, "Base Color")
            set_bsdf_input(bsdf, "Base Color", (0.022, 0.024, 0.029, 1.0))
            set_bsdf_input(bsdf, "Metallic", 0.0)
            set_bsdf_input(bsdf, "Roughness", 0.72)

        m_spoke = bpy.data.materials.get("Material.001")
        if m_spoke:
            bsdf = get_bsdf(m_spoke)
            set_bsdf_input(bsdf, "Base Color", (0.04, 0.044, 0.052, 1.0))
            set_bsdf_input(bsdf, "Metallic", 0.85)
            set_bsdf_input(bsdf, "Roughness", 0.28)

        # Delete leftover Sketchfab_model empties from Momo import
        def del_empty_tree(o):
            for ch in list(o.children):
                del_empty_tree(ch)
            if o.type == "EMPTY":
                bpy.data.objects.remove(o, do_unlink=True)
        del_empty_tree(sw_root)

    # 2. Rebuild Chassis_Alu_Monocoque with lowered center spine tunnel (Zmax=0.225) & tucked roll-hoop (Z=0.90)
    old_ch = bpy.data.objects.get("Chassis_Alu_Monocoque")
    if old_ch:
        bpy.data.objects.remove(old_ch, do_unlink=True)

    mat_alu = bpy.data.materials["MAT_Chassis_Alu"]
    mat_subframe = bpy.data.materials["MAT_Subframe_Steel"]
    mat_eng_dark = bpy.data.materials["MAT_Engine_Dark"]
    bm_ch = bmesh.new()
    # Flat ribbed aluminum floorpan
    add_box(bm_ch, (0.0, -0.06, 0.145), (1.16, 1.18, 0.028), 0)
    # Extruded wide aluminum side sills
    for sx in (1.0, -1.0):
        add_box(bm_ch, (sx * 0.59, -0.06, 0.255), (0.125, 1.24, 0.21), 0)
        add_box(bm_ch, (sx * 0.56, -0.06, 0.365), (0.08, 1.18, 0.03), 0)
        add_box(bm_ch, (sx * 0.52, -0.76, 0.255), (0.09, 0.24, 0.19), 0)
    # Lowered & narrowed center spine tunnel (no clipping through cockpit floor/console!)
    add_box(bm_ch, (0.0, -0.08, 0.185), (0.11, 1.12, 0.08), 0)
    # Front footwell bulkhead (kept below dash Z<=0.36)
    add_box(bm_ch, (0.0, -0.78, 0.26), (1.00, 0.055, 0.20), 0)
    add_box(bm_ch, (0.0, -0.86, 0.22), (0.94, 0.20, 0.14), 0)
    # Front suspension box + crash structure
    add_box(bm_ch, (0.0, -1.12, 0.29), (0.70, 0.44, 0.22), 0)
    add_box(bm_ch, (0.0, -1.48, 0.28), (0.56, 0.34, 0.18), 2)
    # Rear cockpit firewall
    add_box(bm_ch, (0.0, 0.50, 0.42), (1.16, 0.055, 0.56), 0)
    add_box(bm_ch, (0.0, 0.52, 0.72), (0.98, 0.05, 0.12), 0)
    # Roll-over hoop tucked cleanly inside B-pillar structure (Zmax=0.91)
    add_tube(bm_ch, (-0.46, 0.51, 0.72), (-0.40, 0.53, 0.90), 0.020, 12, 1)
    add_tube(bm_ch, (0.46, 0.51, 0.72), (0.40, 0.53, 0.90), 0.020, 12, 1)
    add_tube(bm_ch, (-0.40, 0.53, 0.90), (0.40, 0.53, 0.90), 0.020, 12, 1)
    add_tube(bm_ch, (-0.34, 0.53, 0.89), (-0.36, 0.92, 0.54), 0.017, 10, 1)
    add_tube(bm_ch, (0.34, 0.53, 0.89), (0.36, 0.92, 0.54), 0.017, 10, 1)
    # Rear steel subframe
    for sx in (1.0, -1.0):
        add_box(bm_ch, (sx * 0.39, 1.04, 0.28), (0.055, 1.04, 0.065), 1)
        add_box(bm_ch, (sx * 0.39, 1.18, 0.42), (0.05, 0.38, 0.26), 1)
        add_tube(bm_ch, (sx * 0.48, 0.52, 0.56), (sx * 0.40, 1.20, 0.52), 0.018, 10, 1)
    add_box(bm_ch, (0.0, 1.54, 0.29), (0.84, 0.06, 0.07), 1)
    add_box(bm_ch, (0.0, 0.88, 0.27), (0.78, 0.05, 0.05), 1)

    m_ch = bpy.data.meshes.new("Chassis_Alu_Monocoque")
    bm_ch.to_mesh(m_ch)
    bm_ch.free()
    for m in (mat_alu, mat_subframe, mat_eng_dark):
        m_ch.materials.append(m)
    o_ch = bpy.data.objects.new("Chassis_Alu_Monocoque", m_ch)
    bpy.context.scene.collection.objects.link(o_ch)
    o_ch.parent = grp_chassis

    # 3. Build sleek dark Interior_Center_Console under GRP_Interieur
    old_cc = bpy.data.objects.get("Interior_Center_Console")
    if old_cc:
        bpy.data.objects.remove(old_cc, do_unlink=True)

    mat_console = make_pbr_material("MAT_Interior_Console", (0.025, 0.028, 0.034), metallic=0.04, roughness=0.52)
    mat_console_alu = make_pbr_material("MAT_Interior_Trim_Alu", (0.52, 0.55, 0.60), metallic=0.90, roughness=0.28)
    bm_cc = bmesh.new()
    # Sleek center tunnel console housing (sits below shifter/handbrake/seatbelt buckles, Z=0.22..0.295)
    add_box(bm_cc, (0.0, -0.10, 0.255), (0.142, 0.78, 0.075), 0)
    # Brushed aluminum forward shifter trim surround plate
    add_box(bm_cc, (0.0, -0.29, 0.296), (0.11, 0.22, 0.008), 1)
    # Subtle leather side bolsters along tunnel
    add_box(bm_cc, (-0.074, -0.10, 0.25), (0.012, 0.76, 0.065), 0)
    add_box(bm_cc, (0.074, -0.10, 0.25), (0.012, 0.76, 0.065), 0)
    m_cc = bpy.data.meshes.new("Interior_Center_Console")
    bm_cc.to_mesh(m_cc)
    bm_cc.free()
    m_cc.materials.append(mat_console)
    m_cc.materials.append(mat_console_alu)
    o_cc = bpy.data.objects.new("Interior_Center_Console", m_cc)
    bpy.context.scene.collection.objects.link(o_cc)
    local_cc = grp_interieur.matrix_world.inverted()
    o_cc.data.transform(local_cc)
    o_cc.data.update()
    o_cc.parent = grp_interieur

    # 4. Upgrade all washed-out grey interior materials to rich dark Lotus charcoal/Alcantara/aluminum
    dark_leather_mats = (
        "INT_spotted_plastic.4",
        "INT_spotted_plastic.4_0",
        "INT_aluminium.1_1",
        "INT_aluminium.1_2",
        "INT_grey_plastic",
        "INT_black_plastic.4",
        "CAR_black_plastic.5",
        "INT_black_matte",
        "INT_soft_leather_Skinned",
        "INT_white_plastic.2_0",
    )
    for mname in dark_leather_mats:
        m = bpy.data.materials.get(mname)
        if not m or not m.use_nodes:
            continue
        bsdf = get_bsdf(m)
        disconnect_socket_input(m, bsdf, "Base Color")
        if mname == "INT_grey_plastic":
            set_bsdf_input(bsdf, "Base Color", (0.036, 0.039, 0.046, 1.0))
            set_bsdf_input(bsdf, "Metallic", 0.05)
            set_bsdf_input(bsdf, "Roughness", 0.48)
        elif "spotted" in mname or "soft_leather" in mname:
            set_bsdf_input(bsdf, "Base Color", (0.028, 0.031, 0.037, 1.0))
            set_bsdf_input(bsdf, "Metallic", 0.0)
            set_bsdf_input(bsdf, "Roughness", 0.46)
        elif "aluminium.1_" in mname:
            set_bsdf_input(bsdf, "Base Color", (0.038, 0.041, 0.049, 1.0))
            set_bsdf_input(bsdf, "Metallic", 0.06)
            set_bsdf_input(bsdf, "Roughness", 0.44)
        else:
            set_bsdf_input(bsdf, "Base Color", (0.020, 0.022, 0.026, 1.0))
            set_bsdf_input(bsdf, "Metallic", 0.04)
            set_bsdf_input(bsdf, "Roughness", 0.52)

    m_velvet = bpy.data.materials.get("INT_velvet_black")
    if m_velvet:
        bsdf = get_bsdf(m_velvet)
        disconnect_socket_input(m_velvet, bsdf, "Base Color")
        set_bsdf_input(bsdf, "Base Color", (0.019, 0.021, 0.025, 1.0))
        set_bsdf_input(bsdf, "Metallic", 0.0)
        set_bsdf_input(bsdf, "Roughness", 0.88)

    m_alu_int = bpy.data.materials.get("INT_aluminium.1")
    if m_alu_int:
        bsdf = get_bsdf(m_alu_int)
        disconnect_socket_input(m_alu_int, bsdf, "Base Color")
        set_bsdf_input(bsdf, "Base Color", (0.52, 0.55, 0.60, 1.0))
        set_bsdf_input(bsdf, "Metallic", 0.90)
        set_bsdf_input(bsdf, "Roughness", 0.28)

    m_buckle_btn = bpy.data.materials.get("INT_aluminium.1_0")
    if m_buckle_btn:
        bsdf = get_bsdf(m_buckle_btn)
        disconnect_socket_input(m_buckle_btn, bsdf, "Base Color")
        set_bsdf_input(bsdf, "Base Color", (0.58, 0.03, 0.04, 1.0))
        set_bsdf_input(bsdf, "Metallic", 0.05)
        set_bsdf_input(bsdf, "Roughness", 0.35)

    m_seams = bpy.data.materials.get("INT_seams.1")
    if m_seams:
        bsdf = get_bsdf(m_seams)
        disconnect_socket_input(m_seams, bsdf, "Base Color")
        set_bsdf_input(bsdf, "Base Color", (0.76, 0.55, 0.16, 1.0))
        set_bsdf_input(bsdf, "Metallic", 0.0)
        set_bsdf_input(bsdf, "Roughness", 0.62)

    m_glass_side = bpy.data.materials.get("INT_glass_side")
    if m_glass_side:
        bsdf = get_bsdf(m_glass_side)
        disconnect_socket_input(m_glass_side, bsdf, "Base Color")
        set_bsdf_input(bsdf, "Base Color", (0.03, 0.045, 0.06, 1.0))
        set_bsdf_input(bsdf, "Metallic", 0.0)
        set_bsdf_input(bsdf, "Roughness", 0.04)
        set_bsdf_input(bsdf, "Alpha", 0.22)
        if hasattr(m_glass_side, "blend_method"):
            m_glass_side.blend_method = "BLEND"

    # 5. Move leftover roof headliner, roof header bar & upper roof weather-strip into Dach_Hardtop
    for obj_name, z_t in (("Object_245", 0.95), ("Object_251", 0.95), ("Object_428", 0.94)):
        o = bpy.data.objects.get(obj_name)
        if o:
            split_faces_above_region(o, dach_hardtop, z_thresh=z_t, y_min=-0.24, y_max=0.56)

    # Also move rear upper glass strip Object_223 / Object_424 if it sits above the B-pillar hoop (Z > 0.96),
    # or check: actually Object_223/424 is the rear cabin window behind seats (Y=0.56..0.59, Z=0.85..1.07).
    # In an open-top Exige S2 / Elise, the rear window sits neatly inside the B-pillar buttress up to Z~0.96,
    # whereas Z=0.96..1.07 pokes above the buttress if roof is off! Let's trim Z>0.96 of Object_223 & Object_424 into Dach_Hardtop!
    for glass_name in ("Object_223", "Object_424"):
        go = bpy.data.objects.get(glass_name)
        if go:
            split_faces_above_region(go, dach_hardtop, z_thresh=0.97, y_min=0.50, y_max=0.62)

    # Purge unused blocks
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    bpy.context.view_layer.update()
    print("Cockpit, Momo wheel, console & Targa roof polish complete!")


run()
