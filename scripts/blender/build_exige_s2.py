import math
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler


def get_bsdf(mat):
    if not mat or not mat.use_nodes:
        return None
    return next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def set_bsdf_input(bsdf, name, value):
    if bsdf and name in bsdf.inputs:
        bsdf.inputs[name].default_value = value


def make_pbr_material(name, base_color, metallic=0.0, roughness=0.4, coat=0.0, coat_rough=0.05, alpha=1.0):
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
    if alpha < 1.0:
        mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else "HASHED"
    return mat


def bake_world_transforms_and_normalize_z():
    """Bake matrix_world into mesh data and shift car so lowest tire point sits at Z=0."""
    # First find lowest tire Z across all tire meshes
    tire_names = ["Object_10", "Object_18", "Object_26", "Object_34"]
    min_z = 999.0
    for name in tire_names:
        o = bpy.data.objects.get(name)
        if o and o.type == "MESH":
            for c in o.bound_box:
                wz = (o.matrix_world @ Vector(c)).z
                if wz < min_z:
                    min_z = wz
    z_shift = -min_z if min_z < 900.0 else 0.0

    # Bake world transform into mesh vertices for every mesh under Lotus_Exige_240_3
    exige_root = bpy.data.objects.get("Lotus_Exige_240_3")
    if not exige_root:
        return z_shift

    def collect_meshes(obj, acc):
        if obj.type == "MESH":
            acc.append(obj)
        for ch in obj.children:
            collect_meshes(ch, acc)

    meshes = []
    collect_meshes(exige_root, meshes)
    shift_mat = Matrix.Translation((0.0, 0.0, z_shift))

    for obj in meshes:
        mw = shift_mat @ obj.matrix_world
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
        obj.data.transform(mw)
        obj.data.update()

    return z_shift


def create_empty(name, location=(0.0, 0.0, 0.0), parent=None):
    emp = bpy.data.objects.get(name)
    if emp is None:
        emp = bpy.data.objects.new(name, None)
        emp.empty_display_type = "PLAIN_AXES"
        emp.empty_display_size = 0.08
        bpy.context.scene.collection.objects.link(emp)
    emp.location = Vector(location)
    emp.rotation_euler = (0.0, 0.0, 0.0)
    emp.scale = (1.0, 1.0, 1.0)
    if parent is not None:
        emp.parent = parent
    return emp


def set_origin_to_point(obj, world_pt):
    """Move object origin to world_pt without moving its geometry."""
    p = Vector(world_pt)
    if obj.type == "MESH":
        inv = Matrix.Translation(-p)
        obj.data.transform(inv)
        obj.data.update()
    obj.location = p


def attach_to_group(obj, group_obj):
    """Attach object to group_obj keeping world geometry position."""
    if obj.type == "MESH":
        # Geometry is currently in world space (origin at 0,0,0),
        # so convert vertex coords to group_obj local space.
        inv = Matrix.Translation(-group_obj.matrix_world.translation)
        obj.data.transform(inv)
        obj.data.update()
        obj.location = (0.0, 0.0, 0.0)
    obj.parent = group_obj


def separate_mesh_by_loose_parts(obj):
    """Separate obj into loose-part mesh objects without bpy.ops context pitfalls."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    verts = set(bm.verts)
    components = []
    while verts:
        start = next(iter(verts))
        stack = [start]
        comp_verts = set([start])
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

    for idx, comp_verts in enumerate(components):
        sub_bm = bmesh.new()
        vert_map = {}
        for v in comp_verts:
            nv = sub_bm.verts.new(v.co)
            vert_map[v] = nv
        sub_bm.verts.ensure_lookup_table()

        uv_layer_src = bm.loops.layers.uv.active
        uv_layer_dst = sub_bm.loops.layers.uv.new(uv_layer_src.name) if uv_layer_src else None

        seen_faces = set()
        for v in comp_verts:
            for f in v.link_faces:
                if f in seen_faces:
                    continue
                seen_faces.add(f)
                if all(fv in vert_map for fv in f.verts):
                    try:
                        nf = sub_bm.faces.new([vert_map[fv] for fv in f.verts])
                        nf.material_index = f.material_index
                        nf.smooth = f.smooth
                        if uv_layer_src and uv_layer_dst:
                            for l_src, l_dst in zip(f.loops, nf.loops):
                                l_dst[uv_layer_dst].uv = l_src[uv_layer_src].uv
                    except ValueError:
                        pass

        new_mesh = bpy.data.meshes.new(f"{obj.name}_part{idx}")
        sub_bm.to_mesh(new_mesh)
        sub_bm.free()
        for m in orig_mats:
            new_mesh.materials.append(m)

        new_obj = bpy.data.objects.new(f"{obj.name}_part{idx}", new_mesh)
        col.objects.link(new_obj)
        results.append(new_obj)

    bm.free()
    bpy.data.objects.remove(obj, do_unlink=True)
    return results


def world_center_of_mesh(obj):
    pts = [Vector(c) for c in obj.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))


def world_bounds_of_mesh(obj):
    pts = [Vector(c) for c in obj.bound_box]
    xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


# ---------------------------------------------------------------------------
# Procedural Mechanical Builders (BMesh Helpers)
# ---------------------------------------------------------------------------
def add_box_to_bmesh(bm, center, size, mat_index=0, rot_euler=None):
    sx, sy, sz = size
    mat = Matrix.Translation(center)
    if rot_euler:
        mat = mat @ Euler(rot_euler, "XYZ").to_matrix().to_4x4()
    mat = mat @ Matrix.Diagonal((sx, sy, sz, 1.0))
    ret = bmesh.ops.create_cube(bm, size=1.0, matrix=mat)
    for v in ret["verts"]:
        for f in v.link_faces:
            f.material_index = mat_index


def add_tube_to_bmesh(bm, p1, p2, radius, segments=12, mat_index=0):
    v1 = Vector(p1)
    v2 = Vector(p2)
    diff = v2 - v1
    length = diff.length
    if length < 1e-5:
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
        depth=length,
        matrix=mat,
    )
    for v in ret["verts"]:
        for f in v.link_faces:
            f.material_index = mat_index
            f.smooth = True


def add_cylinder_to_bmesh(bm, center, radius1, radius2, depth, segments=20, axis="Z", mat_index=0, rot_euler=None):
    mat = Matrix.Translation(center)
    if rot_euler:
        mat = mat @ Euler(rot_euler, "XYZ").to_matrix().to_4x4()
    elif axis == "X":
        mat = mat @ Matrix.Rotation(math.pi / 2, 4, "Y")
    elif axis == "Y":
        mat = mat @ Matrix.Rotation(math.pi / 2, 4, "X")
    ret = bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius1,
        radius2=radius2,
        depth=depth,
        matrix=mat,
    )
    for v in ret["verts"]:
        for f in v.link_faces:
            f.material_index = mat_index
            f.smooth = True


def add_coil_spring_to_bmesh(bm, p1, p2, coil_radius=0.032, wire_radius=0.0055, turns=7.5, steps_per_turn=14, mat_index=0):
    v1 = Vector(p1)
    v2 = Vector(p2)
    axis = (v2 - v1)
    length = axis.length
    if length < 1e-4:
        return
    z_dir = axis.normalized()
    up_ref = Vector((0, 1, 0)) if abs(z_dir.y) < 0.9 else Vector((1, 0, 0))
    x_dir = z_dir.cross(up_ref).normalized()
    y_dir = z_dir.cross(x_dir).normalized()

    total_steps = int(turns * steps_per_turn)
    pts = []
    for i in range(total_steps + 1):
        t = i / total_steps
        ang = t * turns * 2.0 * math.pi
        pos = v1 + z_dir * (t * length) + (x_dir * math.cos(ang) + y_dir * math.sin(ang)) * coil_radius
        pts.append(pos)

    seg_sides = 8
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            tangent = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            tangent = (pts[-1] - pts[-2]).normalized()
        else:
            tangent = (pts[i + 1] - pts[i - 1]).normalized()
        n1 = tangent.cross(z_dir)
        if n1.length < 1e-4:
            n1 = tangent.cross(x_dir)
        n1.normalize()
        n2 = tangent.cross(n1).normalized()
        ring = []
        for s in range(seg_sides):
            a = 2.0 * math.pi * s / seg_sides
            vp = p + (n1 * math.cos(a) + n2 * math.sin(a)) * wire_radius
            ring.append(bm.verts.new(vp))
        rings.append(ring)

    for i in range(len(rings) - 1):
        r0 = rings[i]
        r1 = rings[i + 1]
        for s in range(seg_sides):
            sn = (s + 1) % seg_sides
            try:
                f = bm.faces.new((r0[s], r0[sn], r1[sn], r1[s]))
                f.material_index = mat_index
                f.smooth = True
            except ValueError:
                pass


def create_mesh_object(name, bm, materials, parent_group):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for m in materials:
        mesh.materials.append(m)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    attach_to_group(obj, parent_group)
    return obj


# ---------------------------------------------------------------------------
# Main Build Routine
# ---------------------------------------------------------------------------
def build():
    # 1. Bake transforms & normalize lowest tire point to Z = 0.0
    z_shift = bake_world_transforms_and_normalize_z()
    print(f"Normalized car Z shift: {z_shift:.5f}m")

    # 2. Setup clean PBR Materials
    mat_paint = make_pbr_material("MAT_CarPaint", (0.015, 0.017, 0.022), metallic=0.75, roughness=0.18, coat=1.0, coat_rough=0.04)
    mat_rim = make_pbr_material("MAT_Rim", (0.025, 0.028, 0.035), metallic=0.85, roughness=0.28)
    mat_glass = make_pbr_material("MAT_Glass", (0.03, 0.045, 0.06), metallic=0.0, roughness=0.05, coat=0.6, alpha=0.35)
    mat_alu = make_pbr_material("MAT_Chassis_Alu", (0.62, 0.65, 0.69), metallic=0.92, roughness=0.28)
    mat_subframe = make_pbr_material("MAT_Subframe_Steel", (0.28, 0.30, 0.34), metallic=0.85, roughness=0.38)
    mat_carbon = make_pbr_material("MAT_Carbon", (0.032, 0.035, 0.042), metallic=0.25, roughness=0.34, coat=0.45, coat_rough=0.16)
    mat_disc = make_pbr_material("MAT_BrakeDisc", (0.48, 0.50, 0.53), metallic=0.92, roughness=0.26)
    mat_disc_hat = make_pbr_material("MAT_BrakeHat", (0.08, 0.09, 0.11), metallic=0.65, roughness=0.38)
    mat_caliper = make_pbr_material("MAT_BrakeCaliper", (0.65, 0.04, 0.06), metallic=0.45, roughness=0.26, coat=0.75, coat_rough=0.08)
    mat_susp_arm = make_pbr_material("MAT_Suspension_Arm", (0.08, 0.09, 0.11), metallic=0.82, roughness=0.34)
    mat_coil_body = make_pbr_material("MAT_Coilover_Body", (0.88, 0.58, 0.02), metallic=0.40, roughness=0.24)
    mat_coil_spring = make_pbr_material("MAT_Coilover_Spring", (0.72, 0.04, 0.05), metallic=0.22, roughness=0.32)
    mat_eng_alu = make_pbr_material("MAT_Engine_Alu", (0.50, 0.53, 0.56), metallic=0.88, roughness=0.35)
    mat_eng_dark = make_pbr_material("MAT_Engine_Dark", (0.04, 0.042, 0.048), metallic=0.25, roughness=0.52)
    mat_eng_red = make_pbr_material("MAT_Engine_Red", (0.60, 0.035, 0.045), metallic=0.32, roughness=0.30, coat=0.4)
    mat_exhaust = make_pbr_material("MAT_Exhaust", (0.58, 0.49, 0.39), metallic=0.93, roughness=0.24)

    # Upgrade existing materials cleanly
    for mat in list(bpy.data.materials):
        if mat.name.startswith("CAR_chassis"):
            # Replace with MAT_CarPaint on meshes below
            pass
        elif mat.name.startswith("CAR_RIM"):
            pass
        elif mat.name in ("CAR_lights_0", "INT_glass_side", "INT_Vetro", "INT_glass"):
            bsdf = get_bsdf(mat)
            set_bsdf_input(bsdf, "Base Color", (0.03, 0.045, 0.06, 1.0))
            set_bsdf_input(bsdf, "Roughness", 0.04)
            set_bsdf_input(bsdf, "Alpha", 0.35)
            set_bsdf_input(bsdf, "Coat Weight", 0.7)
            if hasattr(mat, "blend_method"):
                mat.blend_method = "BLEND"
        elif mat.name.startswith("CAR_Carbon"):
            bsdf = get_bsdf(mat)
            set_bsdf_input(bsdf, "Base Color", (0.032, 0.035, 0.042, 1.0))
            set_bsdf_input(bsdf, "Metallic", 0.25)
            set_bsdf_input(bsdf, "Roughness", 0.34)
            set_bsdf_input(bsdf, "Coat Weight", 0.45)
        elif mat.name == "INT_white_plastic.2" and mat.use_nodes:
            nt = mat.node_tree
            nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
            nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
            set_bsdf_input(bsdf, "Base Color", (0.85, 0.85, 0.85, 1.0))
            set_bsdf_input(bsdf, "Roughness", 0.45)

    # Swap CAR_chassis* -> MAT_CarPaint and CAR_RIM* -> MAT_Rim on all car meshes
    for obj in bpy.data.objects:
        if obj.type != "MESH" or not obj.data:
            continue
        for idx, m in enumerate(obj.data.materials):
            if not m:
                continue
            if m.name.startswith("CAR_chassis"):
                obj.data.materials[idx] = mat_paint
            elif m.name.startswith("CAR_RIM"):
                obj.data.materials[idx] = mat_rim

    # 3. Create Root & 11 Technical Groups
    root = create_empty("Lotus_Exige_S2", (0.0, 0.0, 0.0))

    grp_front_clam = create_empty("GRP_Karosserie_FrontClam", (0.0, -1.25, 0.44), root)
    grp_heck_clam = create_empty("GRP_Karosserie_HeckClam", (0.0, 1.15, 0.68), root)
    grp_tueren = create_empty("GRP_Karosserie_Tueren", (0.0, 0.0, 0.0), root)
    tuer_links = create_empty("Tuer_Links", (0.72, 0.0, 0.56), grp_tueren)
    tuer_rechts = create_empty("Tuer_Rechts", (-0.72, 0.0, 0.56), grp_tueren)

    grp_dach = create_empty("GRP_Karosserie_Dach", (0.0, 0.12, 0.92), root)
    grp_aero = create_empty("GRP_Aerodynamik", (0.0, 0.0, 0.0), root)
    aero_fluegel = create_empty("Aero_Heckfluegel", (0.0, 1.66, 0.96), grp_aero)
    aero_diffusor = create_empty("Aero_Diffusor", (0.0, 1.53, 0.24), grp_aero)

    grp_raeder = create_empty("GRP_Raeder", (0.0, 0.0, 0.0), root)
    hubs = {
        "VL": Vector((0.7427, -1.1150, 0.3001 + z_shift)),
        "VR": Vector((-0.7427, -1.1148, 0.3001 + z_shift)),
        "HL": Vector((0.7041, 1.2001, 0.3167 + z_shift)),
        "HR": Vector((-0.7041, 1.2003, 0.3167 + z_shift)),
    }
    rad_groups = {k: create_empty(f"Rad_{k}", hubs[k], grp_raeder) for k in ("VL", "VR", "HL", "HR")}

    grp_bremsen = create_empty("GRP_Bremsen", (0.0, 0.0, 0.0), root)
    bremse_groups = {k: create_empty(f"Bremse_{k}", hubs[k], grp_bremsen) for k in ("VL", "VR", "HL", "HR")}

    grp_fahrwerk = create_empty("GRP_Fahrwerk", (0.0, 0.0, 0.0), root)
    fahrwerk_groups = {
        "VL": create_empty("Fahrwerk_VL", (0.52, -1.115, 0.32), grp_fahrwerk),
        "VR": create_empty("Fahrwerk_VR", (-0.52, -1.115, 0.32), grp_fahrwerk),
        "HL": create_empty("Fahrwerk_HL", (0.50, 1.200, 0.34), grp_fahrwerk),
        "HR": create_empty("Fahrwerk_HR", (-0.50, 1.200, 0.34), grp_fahrwerk),
    }

    grp_motor = create_empty("GRP_Motor_Antrieb", (0.0, 1.05, 0.50), root)
    grp_interieur = create_empty("GRP_Interieur", (0.0, -0.08, 0.56), root)
    grp_chassis = create_empty("GRP_Chassis", (0.0, 0.0, 0.0), root)
    bpy.context.view_layer.update()

    # 4. Re-parent existing Sketchfab car meshes into the 11 groups
    def find_descendants_of_old_empty(empty_name):
        # Note: we already unparented meshes in bake_world_transforms_and_normalize_z,
        # so let's classify by exact object name / parent history!
        pass

    # Map mesh object names cleanly based on our verified inventory
    # Doors Left: Object_44..81 (step 3 increments: 44,47,50,53,56,59,62,66,69,72,75,78,81)
    door_l_names = {"Object_44", "Object_47", "Object_50", "Object_53", "Object_56", "Object_59", "Object_62", "Object_66", "Object_69", "Object_72", "Object_75", "Object_78", "Object_81"}
    door_r_names = {"Object_87", "Object_90", "Object_93", "Object_96", "Object_99", "Object_102", "Object_105", "Object_109", "Object_112", "Object_115", "Object_118", "Object_121", "Object_124"}

    wheel_map = {
        "Object_10": "HL", "Object_12": "HL", "Object_14": "HL",
        "Object_18": "VR", "Object_20": "VR", "Object_22": "VR",
        "Object_26": "VL", "Object_28": "VL", "Object_30": "VL",
        "Object_34": "HR", "Object_36": "HR", "Object_38": "HR",
    }

    old_disc_susp = {
        "Object_129", "Object_134", "Object_139", "Object_144",
        "Object_149", "Object_154", "Object_159", "Object_164",
        "Object_370", "Object_340",  # flat engine & old exhaust placeholders (we replace with rich 3D engine & exhaust)
    }

    cockpit_names = {
        "Object_170", "Object_173", "Object_178", "Object_181",
        "Object_186", "Object_189", "Object_192", "Object_195", "Object_198",
        "Object_206", "Object_209", "Object_213", "Object_219",
        "Object_227", "Object_230", "Object_233", "Object_236", "Object_239",
        "Object_242", "Object_245", "Object_248", "Object_251", "Object_254",
        "Object_257", "Object_260", "Object_263", "Object_266", "Object_269",
        "Object_272", "Object_275", "Object_278",
        "Object_282", "Object_285", "Object_288", "Object_291", "Object_294", "Object_297",
        "Object_301", "Object_305", "Object_309", "Object_313", "Object_317",
        "Object_321", "Object_325", "Object_329", "Object_333",
    }
    # Note: Object_202 (INT_Vetro front windshield interior) & Object_223 (INT_Vetro_cockpit rear) -> put with Dach/Front cleanly!

    front_clam_names = {
        "Object_416", "Object_434", "Object_438", "Object_442", "Object_446",
        "Object_450", "Object_453", "Object_456", "Object_459", "Object_462",
        "Object_465", "Object_468", "Object_471", "Object_474", "Object_477",
        "Object_480", "Object_485", "Object_490",
    }

    heck_clam_names = {
        "Object_349", "Object_352", "Object_355", "Object_358", "Object_367",
        "Object_373", "Object_379", "Object_383", "Object_387",
        "Object_392", "Object_396", "Object_400", "Object_404", "Object_408",
        "Object_412", "Object_420", "Object_503", "Object_506", "Object_509",
        "Object_521",
    }

    wing_names = {"Object_514", "Object_517"}
    diffuser_names = {"Object_495", "Object_498"}

    dach_names = {"Object_202", "Object_223", "Object_337", "Object_376", "Object_424", "Object_428"}

    # Assign direct mapped objects
    for name in list(door_l_names):
        o = bpy.data.objects.get(name)
        if o: attach_to_group(o, tuer_links)
    for name in list(door_r_names):
        o = bpy.data.objects.get(name)
        if o: attach_to_group(o, tuer_rechts)
    for name, wkey in wheel_map.items():
        o = bpy.data.objects.get(name)
        if o: attach_to_group(o, rad_groups[wkey])
    for name in cockpit_names:
        o = bpy.data.objects.get(name)
        if o: attach_to_group(o, grp_interieur)
    for name in front_clam_names:
        o = bpy.data.objects.get(name)
        if o: attach_to_group(o, grp_front_clam)
    for name in heck_clam_names:
        o = bpy.data.objects.get(name)
        if o: attach_to_group(o, grp_heck_clam)
    for name in wing_names:
        o = bpy.data.objects.get(name)
        if o: attach_to_group(o, aero_fluegel)
    for name in diffuser_names:
        o = bpy.data.objects.get(name)
        if o: attach_to_group(o, aero_diffusor)
    for name in dach_names:
        o = bpy.data.objects.get(name)
        if o: attach_to_group(o, grp_dach)

    # Remove old placeholder discs/susp/engine/exhaust
    for name in old_disc_susp:
        o = bpy.data.objects.get(name)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)

    # Split and classify composite shell meshes: Object_346, Object_343, Object_361, Object_364
    for comp_name in ("Object_346", "Object_343", "Object_361", "Object_364"):
        comp_obj = bpy.data.objects.get(comp_name)
        if not comp_obj:
            continue
        parts = separate_mesh_by_loose_parts(comp_obj)
        for p in parts:
            cx, cy, cz = world_center_of_mesh(p)
            xmin, xmax, ymin, ymax, zmin, zmax = world_bounds_of_mesh(p)
            # Underbody flat floorpan (spans under cockpit & engine) -> Chassis
            if comp_name == "Object_361" and zmax < 0.30 and (ymax - ymin) > 1.2:
                attach_to_group(p, grp_chassis)
            # Rear parts (y > 0.42)
            elif cy > 0.42:
                attach_to_group(p, grp_heck_clam)
            # Roof & Roof scoop & Upper Windshield Canopy
            elif cz > 0.72 or (comp_name == "Object_343" and ymin > -0.65 and ymax < 0.60 and abs(cx) < 0.72):
                attach_to_group(p, grp_dach)
            # Front parts (y < -0.52)
            elif cy < -0.52:
                attach_to_group(p, grp_front_clam)
            # Side rocker sills & A/B-pillar outer trim (connects front to rear along sides)
            elif abs(cx) > 0.45 and cz < 0.72:
                # Split side rocker sill / pillar trim cleanly to Dach (upper canopy) or HeckClam if rearward
                if zmax > 0.78:
                    attach_to_group(p, grp_dach)
                elif cy > 0.15:
                    attach_to_group(p, grp_heck_clam)
                else:
                    attach_to_group(p, grp_front_clam)
            else:
                attach_to_group(p, grp_dach)

    # 5. Setup high-detail Brakes (from Car Disc Brake Sketchfab_model.001)
    # Source brake parts: Object_4 (pad), Object_6 (disc), Object_7 (vents), Object_8 (hat), Object_10.001 (caliper), Object_11 (caliper pins)
    brake_sources = []
    for src_name, mat_override in [
        ("Object_6", mat_disc),
        ("Object_7", mat_disc_hat),
        ("Object_8", mat_disc_hat),
        ("Object_10.001", mat_caliper),
        ("Object_11", mat_alu),
        ("Object_4", mat_susp_arm),
    ]:
        so = bpy.data.objects.get(src_name)
        if so and so.type == "MESH":
            # Bake its current world transform (it's centered near 0,0,0, normal along X)
            mw = so.matrix_world.copy()
            so.parent = None
            so.matrix_world = Matrix.Identity(4)
            so.data.transform(mw)
            so.data.update()
            # Replace material with clean PBR
            if len(so.data.materials) > 0:
                so.data.materials[0] = mat_override
            else:
                so.data.materials.append(mat_override)
            brake_sources.append(so)

    if brake_sources:
        for wkey, hpos in hubs.items():
            is_left = wkey.endswith("L")
            is_front = wkey.startswith("V")
            scale_f = 0.88 if is_front else 0.90  # ~288mm Exige S2 cross-drilled discs
            bgrp = bremse_groups[wkey]
            # Place slightly inward from tire outer face so rotor sits inside rim barrel
            hub_offset_x = -0.015 if is_left else 0.015
            for idx, so in enumerate(brake_sources):
                dup_mesh = so.data.copy()
                dup_obj = bpy.data.objects.new(f"Brake_{wkey}_{idx}", dup_mesh)
                bpy.context.scene.collection.objects.link(dup_obj)
                # Mirror on X for right side vs left side, rotate caliper toward center of wheelbase
                # Original Car Disc Brake has caliper at -Y and disc normal along X (hat at -X)
                rot_z = math.pi if is_left else 0.0
                # On left (+X) side, hat should face inward (-X) when rot_z=0? Wait: hat in source is at X=-0.041!
                # So for Left (+X side), outer face is +X, inner hat is -X -> rot_z = 0 puts hat inward (-X)!
                #Wait: if front caliper sits toward rear (+Y), and rear caliper sits toward front (-Y):
                # Source caliper is at -Y. Rotate around X by pi if we want caliper at +Y!
                mat_rot = Matrix.Identity(4)
                if not is_left:
                    # Flip X so hat faces +X (inward toward car center on right side!)
                    mat_rot = Matrix.Diagonal((-1.0, 1.0, 1.0, 1.0)) @ mat_rot
                if is_front:
                    # Put front caliper toward rear (+Y)
                    mat_rot = Matrix.Rotation(math.pi, 4, "X") @ mat_rot
                mat_scale = Matrix.Diagonal((scale_f, scale_f, scale_f, 1.0))
                dup_mesh.transform(mat_rot @ mat_scale)
                if not is_left:
                    dup_mesh.flip_normals()
                dup_mesh.update()
                dup_obj.location = (hub_offset_x, 0.0, 0.0)
                dup_obj.parent = bgrp

        # Remove original brake source objects & Sketchfab_model.001 empties
        for so in brake_sources:
            bpy.data.objects.remove(so, do_unlink=True)
    for leftover_name in ("Sketchfab_model.001", "root.001", "GLTF_SceneRootNode.001", "Brake_Caliper_2", "Brake_Disc_1", "Brake_Pads_0", "Lotus_Exige_240_3", "Sketchfab_model", "root", "GLTF_SceneRootNode", "51fbee83c2474f20a036965a1a6b3c9f.fbx_1", "RootNode_2"):
        lo = bpy.data.objects.get(leftover_name)
        if lo:
            # Remove empty wrappers recursively only if they have no remaining mesh children
            pass

    # Clean up all original Sketchfab wrapper empties that have no mesh descendants
    def prune_empty_trees(obj):
        for ch in list(obj.children):
            prune_empty_trees(ch)
        if obj.type == "EMPTY" and not obj.name.startswith(("Lotus_Exige_S2", "GRP_", "Tuer_", "Aero_", "Rad_", "Bremse_", "Fahrwerk_")) and len(obj.children) == 0:
            bpy.data.objects.remove(obj, do_unlink=True)

    for name in [o.name for o in bpy.data.objects]:
        o = bpy.data.objects.get(name)
        if o and o.parent is None and o.name != "Lotus_Exige_S2":
            prune_empty_trees(o)

    # 6. Build GRP_Chassis (Lotus Extruded & Bonded Aluminum Monocoque + Subframe + Roll Hoop)
    bm_ch = bmesh.new()
    # Materials: 0 = mat_alu, 1 = mat_subframe, 2 = mat_eng_dark
    # Flat ribbed aluminum floorpan
    add_box_to_bmesh(bm_ch, (0.0, -0.06, 0.145), (1.16, 1.18, 0.028), 0)
    # Extruded wide aluminum side sills (left & right)
    for sx in (1.0, -1.0):
        add_box_to_bmesh(bm_ch, (sx * 0.59, -0.06, 0.255), (0.125, 1.24, 0.21), 0)
        add_box_to_bmesh(bm_ch, (sx * 0.56, -0.06, 0.365), (0.08, 1.18, 0.03), 0)
        # Front sill taper
        add_box_to_bmesh(bm_ch, (sx * 0.52, -0.76, 0.255), (0.09, 0.24, 0.19), 0)
    # Center extruded spine tunnel
    add_box_to_bmesh(bm_ch, (0.0, -0.08, 0.24), (0.16, 1.12, 0.17), 0)
    # Front footwell bulkhead & pedal bulkhead
    add_box_to_bmesh(bm_ch, (0.0, -0.76, 0.31), (1.02, 0.055, 0.34), 0)
    add_box_to_bmesh(bm_ch, (0.0, -0.84, 0.22), (0.96, 0.20, 0.15), 0)
    # Front suspension pickup aluminum frame + composite crash box
    add_box_to_bmesh(bm_ch, (0.0, -1.12, 0.29), (0.70, 0.44, 0.22), 0)
    add_box_to_bmesh(bm_ch, (0.0, -1.48, 0.28), (0.56, 0.34, 0.18), 2)
    # Rear cockpit bulkhead (firewall)
    add_box_to_bmesh(bm_ch, (0.0, 0.50, 0.42), (1.16, 0.055, 0.56), 0)
    add_box_to_bmesh(bm_ch, (0.0, 0.52, 0.72), (0.98, 0.05, 0.12), 0)
    # Tubular steel roll-over hoop + rear diagonal braces
    add_tube_to_bmesh(bm_ch, (-0.48, 0.50, 0.72), (-0.42, 0.52, 0.99), 0.022, 12, 1)
    add_tube_to_bmesh(bm_ch, (0.48, 0.50, 0.72), (0.42, 0.52, 0.99), 0.022, 12, 1)
    add_tube_to_bmesh(bm_ch, (-0.42, 0.52, 0.99), (0.42, 0.52, 0.99), 0.022, 12, 1)
    add_tube_to_bmesh(bm_ch, (-0.36, 0.52, 0.97), (-0.36, 0.92, 0.54), 0.018, 10, 1)
    add_tube_to_bmesh(bm_ch, (0.36, 0.52, 0.97), (0.36, 0.92, 0.54), 0.018, 10, 1)
    # Galvanized steel rear subframe rails & crossmembers
    for sx in (1.0, -1.0):
        add_box_to_bmesh(bm_ch, (sx * 0.39, 1.04, 0.28), (0.055, 1.04, 0.065), 1)
        add_box_to_bmesh(bm_ch, (sx * 0.39, 1.18, 0.42), (0.05, 0.38, 0.26), 1)
        add_tube_to_bmesh(bm_ch, (sx * 0.48, 0.52, 0.56), (sx * 0.40, 1.20, 0.52), 0.018, 10, 1)
    add_box_to_bmesh(bm_ch, (0.0, 1.54, 0.29), (0.84, 0.06, 0.07), 1)
    add_box_to_bmesh(bm_ch, (0.0, 0.88, 0.27), (0.78, 0.05, 0.05), 1)
    create_mesh_object("Chassis_Alu_Monocoque", bm_ch, [mat_alu, mat_subframe, mat_eng_dark], grp_chassis)

    # 7. Build GRP_Fahrwerk (Double-Wishbone + Bilstein Coilover at all 4 corners)
    for wkey, hpos in hubs.items():
        bm_fw = bmesh.new()
        # Materials: 0 = mat_susp_arm, 1 = mat_alu, 2 = mat_coil_body, 3 = mat_coil_spring
        is_left = wkey.endswith("L")
        is_front = wkey.startswith("V")
        sx = 1.0 if is_left else -1.0

        hub_pt = Vector((hpos.x - sx * 0.06, hpos.y, hpos.z))
        in_x = sx * 0.34 if is_front else sx * 0.37
        y_center = hpos.y

        # CNC Aluminum upright / hub carrier
        add_box_to_bmesh(bm_fw, (hub_pt.x, y_center, hub_pt.z), (0.05, 0.09, 0.21), 1)
        add_cylinder_to_bmesh(bm_fw, (hub_pt.x, y_center, hub_pt.z), 0.045, 0.045, 0.06, 16, "X", 1)

        # Lower A-arm (two tubular legs meeting at lower ball joint)
        low_ball = (hub_pt.x, y_center, hub_pt.z - 0.09)
        add_tube_to_bmesh(bm_fw, (in_x, y_center - 0.16, hub_pt.z - 0.08), low_ball, 0.012, 10, 0)
        add_tube_to_bmesh(bm_fw, (in_x, y_center + 0.16, hub_pt.z - 0.08), low_ball, 0.012, 10, 0)

        # Upper A-arm
        up_ball = (hub_pt.x - sx * 0.015, y_center, hub_pt.z + 0.10)
        add_tube_to_bmesh(bm_fw, (in_x, y_center - 0.13, hub_pt.z + 0.08), up_ball, 0.011, 10, 0)
        add_tube_to_bmesh(bm_fw, (in_x, y_center + 0.13, hub_pt.z + 0.08), up_ball, 0.011, 10, 0)

        # Tie rod / toe link
        tie_y = y_center + (0.09 if is_front else -0.10)
        add_tube_to_bmesh(bm_fw, (in_x, tie_y, hub_pt.z - 0.02), (hub_pt.x, tie_y, hub_pt.z - 0.02), 0.008, 8, 1)

        # Bilstein Coilover Damper + Eibach Helical Spring
        shock_bot = (hub_pt.x - sx * 0.12, y_center, hub_pt.z - 0.06)
        shock_top = (in_x + sx * 0.04, y_center, hub_pt.z + 0.24)
        add_tube_to_bmesh(bm_fw, shock_bot, shock_top, 0.019, 12, 2)
        s_vec = Vector(shock_top) - Vector(shock_bot)
        sp1 = Vector(shock_bot) + s_vec * 0.16
        sp2 = Vector(shock_bot) + s_vec * 0.84
        add_coil_spring_to_bmesh(bm_fw, sp1, sp2, coil_radius=0.030, wire_radius=0.0055, turns=7.0, steps_per_turn=12, mat_index=3)

        create_mesh_object(f"Fahrwerk_Mesh_{wkey}", bm_fw, [mat_susp_arm, mat_alu, mat_coil_body, mat_coil_spring], fahrwerk_groups[wkey])

    # 8. Build GRP_Motor_Antrieb (1.8L Toyota 2ZZ-GE + Eaton M62 Supercharger + Chargecooler + 6-Speed Transaxle + Exhaust)
    bm_eng = bmesh.new()
    # Materials: 0 = mat_eng_alu, 1 = mat_eng_dark, 2 = mat_eng_red, 3 = mat_exhaust, 4 = mat_alu
    # Transverse I4 block (center slightly toward right/center, gearbox toward left +X)
    add_box_to_bmesh(bm_eng, (-0.06, 1.06, 0.42), (0.38, 0.23, 0.23), 0)
    # Oil pan / baffled sump
    add_box_to_bmesh(bm_eng, (-0.06, 1.06, 0.27), (0.35, 0.21, 0.075), 1)
    # Cylinder head + red 2ZZ-GE DOHC cam cover
    add_box_to_bmesh(bm_eng, (-0.06, 1.06, 0.58), (0.39, 0.22, 0.09), 0)
    add_box_to_bmesh(bm_eng, (-0.06, 1.06, 0.65), (0.37, 0.19, 0.055), 2)
    # 4 ignition coil packs along cam cover
    for ci in range(4):
        cx = -0.19 + ci * 0.088
        add_cylinder_to_bmesh(bm_eng, (cx, 1.06, 0.69), 0.018, 0.018, 0.035, 12, "Z", 1)
    # Eaton M62 Roots Supercharger (front-top of block)
    add_cylinder_to_bmesh(bm_eng, (-0.06, 0.87, 0.58), 0.072, 0.072, 0.28, 16, "X", 4)
    add_cylinder_to_bmesh(bm_eng, (-0.25, 0.87, 0.58), 0.038, 0.038, 0.09, 14, "X", 1)
    # Supercharger drive pulley + crankshaft pulley + alternator pulley
    add_cylinder_to_bmesh(bm_eng, (-0.30, 0.87, 0.58), 0.042, 0.042, 0.025, 16, "X", 2)
    add_cylinder_to_bmesh(bm_eng, (-0.28, 1.06, 0.37), 0.055, 0.055, 0.028, 16, "X", 1)
    add_cylinder_to_bmesh(bm_eng, (-0.26, 0.94, 0.46), 0.045, 0.045, 0.06, 14, "X", 1)
    # Top-mounted Chargecooler / Intercooler + "SUPERCHARGED" Plenum
    add_box_to_bmesh(bm_eng, (-0.05, 0.96, 0.74), (0.34, 0.22, 0.075), 4)
    # Chargecooler cooling fins detail
    for fi in range(7):
        add_box_to_bmesh(bm_eng, (-0.18 + fi * 0.043, 0.96, 0.785), (0.012, 0.20, 0.018), 1)
    # Intake runners curving from chargecooler into cylinder head
    for ci in range(4):
        cx = -0.19 + ci * 0.088
        add_tube_to_bmesh(bm_eng, (cx, 0.91, 0.72), (cx, 0.96, 0.62), 0.021, 10, 4)

    # 6-speed C64 Transaxle Gearbox (+X side of engine)
    add_cylinder_to_bmesh(bm_eng, (0.24, 1.08, 0.41), 0.125, 0.095, 0.26, 16, "X", 0)
    add_box_to_bmesh(bm_eng, (0.22, 1.15, 0.36), (0.20, 0.16, 0.16), 0)
    # Rear CV Driveshafts extending toward rear wheel hubs
    add_tube_to_bmesh(bm_eng, (0.18, 1.19, 0.35), (0.60, 1.20, 0.32), 0.018, 10, 1)
    add_tube_to_bmesh(bm_eng, (-0.02, 1.19, 0.35), (-0.60, 1.20, 0.32), 0.018, 10, 1)

    # 4-into-1 Tubular Stainless Exhaust Header -> Catalytic -> Transverse Rear Silencer -> Dual Tips
    for ci in range(4):
        cx = -0.19 + ci * 0.088
        add_tube_to_bmesh(bm_eng, (cx, 1.16, 0.56), (cx * 0.45, 1.32, 0.44), 0.017, 10, 3)
        add_tube_to_bmesh(bm_eng, (cx * 0.45, 1.32, 0.44), (0.0, 1.38, 0.30), 0.017, 10, 3)
    add_tube_to_bmesh(bm_eng, (0.0, 1.38, 0.30), (0.0, 1.50, 0.25), 0.032, 12, 3)
    # Transverse rear silencer box
    add_cylinder_to_bmesh(bm_eng, (0.0, 1.56, 0.24), 0.075, 0.075, 0.46, 16, "X", 3)
    # Central dual exhaust tailpipes (exiting cleanly at Y=1.74, Z=0.225 inside diffuser cutout)
    for tx in (-0.038, 0.038):
        add_tube_to_bmesh(bm_eng, (tx, 1.58, 0.235), (tx, 1.75, 0.225), 0.026, 14, 4)

    create_mesh_object("Engine_2ZZ_GE_Supercharged", bm_eng, [mat_eng_alu, mat_eng_dark, mat_eng_red, mat_exhaust, mat_alu], grp_motor)

    # 9. Add Lotus machined aluminum footwell pedals to GRP_Interieur
    bm_ped = bmesh.new()
    for px, pz, w in ((0.18, 0.25, 0.042), (0.25, 0.27, 0.055), (0.33, 0.27, 0.048)):
        add_box_to_bmesh(bm_ped, (px, -0.68, pz), (w, 0.014, 0.085), 0, rot_euler=(-0.35, 0.0, 0.0))
        add_tube_to_bmesh(bm_ped, (px, -0.68, pz + 0.02), (px, -0.71, pz + 0.14), 0.007, 8, 0)
    create_mesh_object("Interior_Alu_Pedals", bm_ped, [mat_alu], grp_interieur)

    # Purge unused orphan data blocks
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)

    print("Build complete! Top-level children of Lotus_Exige_S2:")
    for ch in root.children:
        print(" -", ch.name, f"(children={len(ch.children)})")


build()
