"""Generate a first-pass MANUKA outfit variant inside Blender.

Run with Blender, for example:
  blender.exe MANUKA.blend --background --python build-manuka-outfit.py -- \
    --preset casual-streetwear \
    --output MANUKA_casual-streetwear.blend \
    --vrm-output sarah-casual-streetwear.vrm

This script creates editable first-pass garments around MANUKA's actual rig and body
geometry. Fitted pieces reuse MANUKA's existing skinned clothing where practical,
while jackets and sleeves use masked body-surface shells so they follow the avatar
instead of floating as primitive blocks. Final visual tuning in Blender is still
expected before production VRM export.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

PRESETS = {
    "casual-streetwear",
    "cafe-maid",
    "sporty-athleisure",
    "elegant-evening",
    "cozy-sweater",
    "futuristic-idol-techwear",
}

ORIGINAL_COSTUME = {
    "Manuka_costume_apron",
    "Manuka_costume_apron_nameplate",
    "Manuka_costume_bracelet",
    "Manuka_costume_shirt",
    "Manuka_costume_shoes",
    "Manuka_costume_shorts",
    "Manuka_costume_tie",
    "Manuka_underwear_stocking",
}

MATERIAL_COLORS = {
    "cream": (0.92, 0.84, 0.74, 1.0),
    "white": (0.97, 0.95, 0.91, 1.0),
    "black": (0.045, 0.038, 0.045, 1.0),
    "soft_brown": (0.24, 0.14, 0.11, 1.0),
    "honey_amber": (0.88, 0.47, 0.10, 1.0),
}

def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", required=True, choices=sorted(PRESETS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--vrm-output", default="")
    return parser.parse_args(argv)

def find_armature():
    required = {
        "Hips", "Spine", "Chest", "Neck", "Head",
        "UpperArm_L", "UpperArm_R", "UpperLeg_L", "UpperLeg_R",
    }
    candidates = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    for obj in candidates:
        if required.issubset(set(obj.pose.bones.keys())):
            return obj
    if candidates:
        return candidates[0]
    raise RuntimeError("Could not find MANUKA armature.")

def get_object(name):
    return bpy.data.objects.get(name)

def bone(armature, name):
    pose_bone = armature.pose.bones.get(name)
    if pose_bone is None:
        raise RuntimeError(f"Required MANUKA bone not found: {name}")
    return pose_bone

def bone_head(armature, name):
    return armature.matrix_world @ bone(armature, name).head

def bone_tail(armature, name):
    return armature.matrix_world @ bone(armature, name).tail

def bone_center(armature, name):
    return (bone_head(armature, name) + bone_tail(armature, name)) * 0.5

def material(name, color_name, metallic=0.0, roughness=0.5):
    mat_name = f"SarahOutfit_{name}"
    existing = bpy.data.materials.get(mat_name)
    if existing:
        return existing
    mat = bpy.data.materials.new(mat_name)
    mat.diffuse_color = MATERIAL_COLORS[color_name]
    mat.use_nodes = True
    node = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if node:
        node.inputs["Base Color"].default_value = MATERIAL_COLORS[color_name]
        node.inputs["Metallic"].default_value = metallic
        node.inputs["Roughness"].default_value = roughness
    return mat

def move_to_collection(obj, collection):
    for coll in list(obj.users_collection):
        coll.objects.unlink(obj)
    collection.objects.link(obj)

def parent_to_bone(obj, armature, bone_name):
    world = obj.matrix_world.copy()
    obj.parent = armature
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_world = world

def finish_mesh(obj, collection, mat, armature, parent_bone, bevel=0.015):
    move_to_collection(obj, collection)
    if obj.data and hasattr(obj.data, "materials"):
        obj.data.materials.append(mat)
    if bevel > 0:
        modifier = obj.modifiers.new("SarahOutfit_Bevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
    parent_to_bone(obj, armature, parent_bone)
    obj["sarah_outfit_generated"] = True
    return obj

def add_box(name, center, size, mat, collection, armature, parent_bone,
            rotation=(0.0, 0.0, 0.0), bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(location=center, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish_mesh(obj, collection, mat, armature, parent_bone, bevel)

def add_cylinder_between(name, start, end, radius, mat, collection, armature,
                         parent_bone, radius_scale=(1.0, 1.0)):
    vector = end - start
    length = max(vector.length, 0.001)
    center = (start + end) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=length, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(vector.normalized())
    obj.scale.x *= radius_scale[0]
    obj.scale.y *= radius_scale[1]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish_mesh(obj, collection, mat, armature, parent_bone, bevel=radius * 0.08)

def add_cone(name, center, radius_top, radius_bottom, height, mat, collection,
             armature, parent_bone="Hips"):
    bpy.ops.mesh.primitive_cone_add(
        vertices=64,
        radius1=radius_bottom,
        radius2=radius_top,
        depth=height,
        location=center,
    )
    obj = bpy.context.object
    obj.name = name
    return finish_mesh(obj, collection, mat, armature, parent_bone, bevel=0.012)

def add_sphere(name, center, scale, mat, collection, armature, parent_bone):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish_mesh(obj, collection, mat, armature, parent_bone, bevel=0.0)

def add_torus(name, center, major_radius, minor_radius, mat, collection,
              armature, parent_bone, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=48,
        minor_segments=12,
        location=center,
        rotation=rotation,
    )
    obj = bpy.context.object
    obj.name = name
    return finish_mesh(obj, collection, mat, armature, parent_bone, bevel=0.0)

def add_bow(prefix, center, size, mat, collection, armature, parent_bone):
    add_box(
        f"{prefix}_L",
        center + Vector((-size * 0.55, 0.0, 0.0)),
        (size, size * 0.25, size * 0.55),
        mat, collection, armature, parent_bone,
        rotation=(0.0, 0.0, math.radians(20)),
        bevel=size * 0.08,
    )
    add_box(
        f"{prefix}_R",
        center + Vector((size * 0.55, 0.0, 0.0)),
        (size, size * 0.25, size * 0.55),
        mat, collection, armature, parent_bone,
        rotation=(0.0, 0.0, math.radians(-20)),
        bevel=size * 0.08,
    )
    add_sphere(
        f"{prefix}_Center", center,
        (size * 0.24, size * 0.16, size * 0.24),
        mat, collection, armature, parent_bone,
    )

def hide_original_costume():
    for name in ORIGINAL_COSTUME:
        obj = get_object(name)
        if obj:
            obj.hide_render = True
            obj.hide_viewport = True
    for name in ("Manuka_underwear_bra", "Manuka_underwear_panty"):
        obj = get_object(name)
        if obj:
            obj.hide_render = False
            obj.hide_viewport = False

def set_single_material(obj, mat):
    if not obj.data or not hasattr(obj.data, "materials"):
        return
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    if hasattr(obj.data, "polygons"):
        for polygon in obj.data.polygons:
            polygon.material_index = 0

def duplicate_rigged_piece(source_name, new_name, collection, mat=None):
    source = get_object(source_name)
    if source is None:
        raise RuntimeError(f"Required MANUKA source object not found: {source_name}")

    obj = source.copy()
    obj.data = source.data.copy() if source.data else None
    obj.name = new_name
    move_to_collection(obj, collection)

    obj.hide_viewport = False
    obj.hide_render = False
    try:
        obj.hide_set(False)
    except RuntimeError:
        pass

    if mat is not None:
        set_single_material(obj, mat)

    obj["sarah_outfit_generated"] = True
    obj["sarah_outfit_source"] = source_name
    return obj

def group_indices(obj, prefixes):
    prefixes = tuple(prefixes)
    return {
        group.index
        for group in obj.vertex_groups
        if any(group.name == prefix or group.name.startswith(prefix) for prefix in prefixes)
    }

def has_group_weight(vertex, indices, threshold=0.08):
    return any(
        membership.group in indices and membership.weight >= threshold
        for membership in vertex.groups
    )

def body_shell(
    body,
    name,
    collection,
    mat,
    keep_vertex,
    thickness,
):
    obj = body.copy()
    obj.data = body.data.copy()
    obj.name = name
    move_to_collection(obj, collection)
    obj.hide_viewport = False
    obj.hide_render = False
    try:
        obj.hide_set(False)
    except RuntimeError:
        pass

    set_single_material(obj, mat)

    keep_group = obj.vertex_groups.get("SarahOutfitKeep")
    if keep_group is None:
        keep_group = obj.vertex_groups.new(name="SarahOutfitKeep")

    keep_indices = []
    for vertex in obj.data.vertices:
        world_co = obj.matrix_world @ vertex.co
        if keep_vertex(obj, vertex, world_co):
            keep_indices.append(vertex.index)

    if not keep_indices:
        raise RuntimeError(f"{name} mask selected no body vertices.")

    keep_group.add(keep_indices, 1.0, "REPLACE")

    mask = obj.modifiers.new("SarahOutfit_Mask", "MASK")
    mask.vertex_group = keep_group.name

    smooth = obj.modifiers.new("SarahOutfit_Smooth", "SMOOTH")
    smooth.factor = 0.12
    smooth.iterations = 2

    solidify = obj.modifiers.new("SarahOutfit_Thickness", "SOLIDIFY")
    solidify.thickness = thickness
    solidify.offset = 1.0
    solidify.use_rim = True
    if hasattr(solidify, "use_even_offset"):
        solidify.use_even_offset = True

    for polygon in obj.data.polygons:
        polygon.use_smooth = True

    obj["sarah_outfit_generated"] = True
    obj["sarah_outfit_body_shell"] = True
    return obj

def add_armature_modifier(obj, armature):
    modifier = obj.modifiers.new("SarahOutfit_Armature", "ARMATURE")
    modifier.object = armature
    obj.parent = armature
    return modifier

def add_open_jacket_shell(name, body, armature, collection, mat, m):
    """Create a clean open-front cropped jacket shell with smooth authored edges."""
    hips, chest, neck = m["hips"], m["chest"], m["neck"]
    sw, hw, depth, th = (
        m["shoulder_width"],
        m["hip_width"],
        m["depth"],
        m["torso_height"],
    )

    z_levels = [
        hips.z + th * 0.17,
        hips.z + th * 0.34,
        chest.z + th * 0.02,
        neck.z - th * 0.10,
    ]

    def band_profile(z_value):
        points = []
        x_limit = sw * 0.54
        band = max(th * 0.065, 0.025)
        for vertex in body.data.vertices:
            world = body.matrix_world @ vertex.co
            if abs(world.z - z_value) > band:
                continue
            if abs(world.x - chest.x) > x_limit:
                continue
            points.append(world)

        if not points:
            return sw * 0.29, max(depth * 0.62, 0.09)

        x_radius = max(abs(point.x - chest.x) for point in points)
        y_radius = max(abs(point.y - chest.y) for point in points)
        return (
            max(x_radius * 1.055, sw * 0.22),
            max(y_radius * 1.075, depth * 0.54),
        )

    profiles = [band_profile(z_value) for z_value in z_levels]

    # Keep a generous open front so the cream crop top reads clearly.
    gap_angle = math.radians(42)
    angular_segments = 20
    angles = [
        (math.pi + gap_angle)
        + ((2 * math.pi - 2 * gap_angle) * index / (angular_segments - 1))
        for index in range(angular_segments)
    ]

    vertices = []
    for ring_index, z_value in enumerate(z_levels):
        x_radius, y_radius = profiles[ring_index]

        # Slight garment shaping: fitted waist, relaxed chest/shoulder area.
        if ring_index == 0:
            x_radius *= 1.02
            y_radius *= 1.02
        elif ring_index == 1:
            x_radius *= 1.035
            y_radius *= 1.035
        elif ring_index == 2:
            x_radius *= 1.07
            y_radius *= 1.08
        else:
            x_radius *= 1.10
            y_radius *= 1.08

        for angle in angles:
            world = Vector((
                chest.x + math.sin(angle) * x_radius,
                chest.y + math.cos(angle) * y_radius,
                z_value,
            ))
            vertices.append(armature.matrix_world.inverted() @ world)

    faces = []
    for ring_index in range(len(z_levels) - 1):
        base = ring_index * angular_segments
        next_base = (ring_index + 1) * angular_segments
        for angle_index in range(angular_segments - 1):
            a = base + angle_index
            b = base + angle_index + 1
            c_idx = next_base + angle_index + 1
            d = next_base + angle_index
            faces.append((a, b, c_idx, d))

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    set_single_material(obj, mat)

    hips_group = obj.vertex_groups.new(name="Hips")
    spine_group = obj.vertex_groups.new(name="Spine")
    chest_group = obj.vertex_groups.new(name="Chest")

    ring_weights = (
        ((hips_group, 0.70), (spine_group, 0.30)),
        ((hips_group, 0.25), (spine_group, 0.75)),
        ((spine_group, 0.25), (chest_group, 0.75)),
        ((chest_group, 1.00),),
    )
    for ring_index, weights in enumerate(ring_weights):
        indices = list(range(
            ring_index * angular_segments,
            (ring_index + 1) * angular_segments,
        ))
        for group, weight in weights:
            group.add(indices, weight, "REPLACE")

    add_armature_modifier(obj, armature)

    subdivision = obj.modifiers.new("SarahOutfit_Subdivision", "SUBSURF")
    subdivision.levels = 2
    subdivision.render_levels = 2

    solidify = obj.modifiers.new("SarahOutfit_Thickness", "SOLIDIFY")
    solidify.thickness = max(sw * 0.013, 0.0045)
    solidify.offset = 1.0
    solidify.use_rim = True
    if hasattr(solidify, "use_even_offset"):
        solidify.use_even_offset = True

    for polygon in mesh.polygons:
        polygon.use_smooth = True

    obj["sarah_outfit_generated"] = True
    obj["sarah_outfit_preset"] = "casual-streetwear"
    return obj

def add_tapered_sleeve(name, armature, side, collection, mat, m):
    """Create one smooth skinned sleeve with deliberate shoulder-to-wrist taper."""
    upper_name = f"UpperArm_{side}"
    lower_name = f"LowerArm_{side}"
    hand_name = f"Hand_{side}"

    shoulder = bone_head(armature, upper_name)
    elbow = bone_tail(armature, upper_name)
    wrist = bone_head(armature, hand_name)

    sw = m["shoulder_width"]
    upper_length = max((elbow - shoulder).length, 0.10)
    lower_length = max((wrist - elbow).length, 0.10)

    ring_points = [
        shoulder.lerp(elbow, 0.04),
        shoulder.lerp(elbow, 0.38),
        shoulder.lerp(elbow, 0.76),
        elbow.lerp(wrist, 0.08),
        elbow.lerp(wrist, 0.46),
        elbow.lerp(wrist, 0.82),
        elbow.lerp(wrist, 0.955),
    ]

    base_radius = max(min(upper_length, lower_length) * 0.19, sw * 0.060)
    radii = [
        base_radius * 1.10,
        base_radius * 1.06,
        base_radius * 0.98,
        base_radius * 0.93,
        base_radius * 0.84,
        base_radius * 0.73,
        base_radius * 0.64,
    ]

    radial_segments = 20
    vertices = []

    for ring_index, center in enumerate(ring_points):
        if ring_index == 0:
            tangent = ring_points[1] - center
        elif ring_index == len(ring_points) - 1:
            tangent = center - ring_points[ring_index - 1]
        else:
            tangent = ring_points[ring_index + 1] - ring_points[ring_index - 1]
        tangent.normalize()

        reference = Vector((0.0, 0.0, 1.0))
        if abs(tangent.dot(reference)) > 0.92:
            reference = Vector((0.0, 1.0, 0.0))

        axis_a = tangent.cross(reference).normalized()
        axis_b = tangent.cross(axis_a).normalized()

        radius = radii[ring_index]
        for segment in range(radial_segments):
            angle = (2 * math.pi * segment) / radial_segments
            # Slightly flatter front/back than vertical to read as cloth, not pipe.
            offset = (
                axis_a * math.cos(angle) * radius * 0.94
                + axis_b * math.sin(angle) * radius * 1.04
            )
            world = center + offset
            vertices.append(armature.matrix_world.inverted() @ world)

    faces = []
    for ring_index in range(len(ring_points) - 1):
        base = ring_index * radial_segments
        next_base = (ring_index + 1) * radial_segments
        for segment in range(radial_segments):
            next_segment = (segment + 1) % radial_segments
            faces.append((
                base + segment,
                base + next_segment,
                next_base + next_segment,
                next_base + segment,
            ))

    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    set_single_material(obj, mat)

    upper_group = obj.vertex_groups.new(name=upper_name)
    lower_group = obj.vertex_groups.new(name=lower_name)

    upper_weights = (1.0, 1.0, 0.88, 0.50, 0.10, 0.0, 0.0)
    for ring_index, upper_weight in enumerate(upper_weights):
        indices = list(range(
            ring_index * radial_segments,
            (ring_index + 1) * radial_segments,
        ))
        lower_weight = 1.0 - upper_weight
        if upper_weight > 0:
            upper_group.add(indices, upper_weight, "REPLACE")
        if lower_weight > 0:
            lower_group.add(indices, lower_weight, "REPLACE")

    add_armature_modifier(obj, armature)

    subdivision = obj.modifiers.new("SarahOutfit_Subdivision", "SUBSURF")
    subdivision.levels = 2
    subdivision.render_levels = 2

    solidify = obj.modifiers.new("SarahOutfit_Thickness", "SOLIDIFY")
    solidify.thickness = max(sw * 0.010, 0.0035)
    solidify.offset = 1.0
    solidify.use_rim = True
    if hasattr(solidify, "use_even_offset"):
        solidify.use_even_offset = True

    for polygon in mesh.polygons:
        polygon.use_smooth = True

    obj["sarah_outfit_generated"] = True
    obj["sarah_outfit_preset"] = "casual-streetwear"
    return obj

def metrics(armature):
    hips = bone_center(armature, "Hips")
    chest = bone_center(armature, "Chest")
    neck = bone_head(armature, "Neck")
    head = bone_center(armature, "Head")
    shoulder_l = bone_head(armature, "UpperArm_L")
    shoulder_r = bone_head(armature, "UpperArm_R")
    hip_l = bone_head(armature, "UpperLeg_L")
    hip_r = bone_head(armature, "UpperLeg_R")

    shoulder_width = max((shoulder_l - shoulder_r).length, 0.24)
    hip_width = max((hip_l - hip_r).length, shoulder_width * 0.55)
    torso_height = max(neck.z - hips.z, 0.38)
    depth = shoulder_width * 0.34

    return {
        "hips": hips,
        "chest": chest,
        "neck": neck,
        "head": head,
        "shoulder_width": shoulder_width,
        "hip_width": hip_width,
        "torso_height": torso_height,
        "depth": depth,
    }

def add_basic_shoes(prefix, armature, collection, mat, chunky=False, heels=False):
    for side, bone_name in (("L", "Foot_L"), ("R", "Foot_R")):
        foot = bone_center(armature, bone_name)
        width = 0.12 if chunky else 0.09
        length = 0.25 if chunky else 0.21
        height = 0.11 if chunky else 0.07
        add_box(
            f"{prefix}_Shoe_{side}",
            foot + Vector((0, -0.03, 0.02)),
            (width, length, height),
            mat, collection, armature, bone_name,
            bevel=0.025,
        )
        if heels:
            add_box(
                f"{prefix}_Heel_{side}",
                foot + Vector((0, 0.05, -0.02)),
                (0.035, 0.045, 0.11),
                mat, collection, armature, bone_name,
                bevel=0.006,
            )

def add_arm_sleeves(prefix, armature, collection, mat, oversized=False, short=False):
    for side in ("L", "R"):
        upper = f"UpperArm_{side}"
        lower = f"LowerArm_{side}"
        u0, u1 = bone_head(armature, upper), bone_tail(armature, upper)
        radius = max((u1 - u0).length * (0.23 if oversized else 0.16), 0.045)
        if short:
            u1 = u0.lerp(u1, 0.55)
        add_cylinder_between(
            f"{prefix}_UpperSleeve_{side}",
            u0, u1, radius, mat, collection, armature, upper,
            radius_scale=(1.18 if oversized else 1.0, 1.18 if oversized else 1.0),
        )
        if not short:
            l0, l1 = bone_head(armature, lower), bone_tail(armature, lower)
            add_cylinder_between(
                f"{prefix}_LowerSleeve_{side}",
                l0, l1, radius * (0.92 if oversized else 0.75),
                mat, collection, armature, lower,
                radius_scale=(1.15 if oversized else 1.0, 1.15 if oversized else 1.0),
            )

def add_socks(prefix, armature, collection, mat, tall=True):
    for side in ("L", "R"):
        bone_name = f"LowerLeg_{side}"
        start, end = bone_head(armature, bone_name), bone_tail(armature, bone_name)
        if not tall:
            start = start.lerp(end, 0.55)
        add_cylinder_between(
            f"{prefix}_Sock_{side}",
            start, end,
            max((end - start).length * 0.10, 0.045),
            mat, collection, armature, bone_name,
            radius_scale=(1.05, 0.94),
        )

def build_casual_streetwear(armature, coll, m):
    """Body-fitted streetwear pass based on the supplied reference.

    Reuse MANUKA's existing fitted bra/shorts/shoes/tie for reliable skinning and
    proportions, then add a separate open jacket shell around the body and arms.
    This avoids the large primitive cylinders/boxes from the original prototype.
    """
    cream = material("Casual_Cream", "cream", metallic=0.0, roughness=0.58)
    black = material("Casual_Black", "black", metallic=0.0, roughness=0.62)
    amber = material("Casual_Amber", "honey_amber", metallic=0.08, roughness=0.42)

    hips, chest, neck = m["hips"], m["chest"], m["neck"]
    sw, hw, depth, th = (
        m["shoulder_width"],
        m["hip_width"],
        m["depth"],
        m["torso_height"],
    )

    body = get_object("Manuka_body")
    if body is None:
        raise RuntimeError("Required MANUKA body object not found: Manuka_body")

    # Use MANUKA's own fitted geometry wherever possible. These pieces already
    # deform correctly with the avatar and immediately look less blocky.
    top = duplicate_rigged_piece(
        "Manuka_underwear_bra",
        "Casual_CropTop",
        coll,
        cream,
    )
    shorts = duplicate_rigged_piece(
        "Manuka_costume_shorts",
        "Casual_FittedShorts",
        coll,
        black,
    )
    shoes = duplicate_rigged_piece(
        "Manuka_costume_shoes",
        "Casual_FittedShoes",
        coll,
        black,
    )
    tie = duplicate_rigged_piece(
        "Manuka_costume_tie",
        "Casual_AmberNecktie",
        coll,
        amber,
    )

    # Hide the original underwear top now that the cream duplicate replaces it.
    original_bra = get_object("Manuka_underwear_bra")
    if original_bra:
        original_bra.hide_viewport = True
        original_bra.hide_render = True

    # Retain references so Blender does not optimize away user-facing object names.
    for piece in (top, shorts, shoes, tie):
        piece["sarah_outfit_preset"] = "casual-streetwear"

    # Clean authored garment meshes replace the earlier masked body shell.
    # Their edge loops are explicit, so the neckline/front/hem no longer inherit
    # jagged cuts from MANUKA's body topology.
    add_open_jacket_shell(
        "Casual_OpenJacketBody",
        body,
        armature,
        coll,
        black,
        m,
    )

    for side in ("L", "R"):
        add_tapered_sleeve(
            f"Casual_JacketSleeve_{side}",
            armature,
            side,
            coll,
            black,
            m,
        )

    # Thin cuffs sit just inside the wrist and visually finish the tapered sleeves.
    cuff_major = max(sw * 0.055, 0.022)
    cuff_minor = max(sw * 0.006, 0.0025)
    for side, hand_name, forearm_name in (
        ("L", "Hand_L", "LowerArm_L"),
        ("R", "Hand_R", "LowerArm_R"),
    ):
        wrist = bone_head(armature, hand_name).lerp(
            bone_head(armature, forearm_name),
            0.035,
        )
        add_torus(
            f"Casual_Cuff_{side}",
            wrist,
            cuff_major,
            cuff_minor,
            black,
            coll,
            armature,
            forearm_name,
            rotation=(0.0, math.radians(90), 0.0),
        )

    # Small lapels add the street-jacket silhouette without dominating the fit.
    lapel_z = chest.z + th * 0.08
    lapel_y = chest.y - depth * 0.60
    lapel_w = sw * 0.085
    lapel_h = th * 0.18
    lapel_d = max(depth * 0.060, 0.007)
    for side, sign in (("L", -1), ("R", 1)):
        add_box(
            f"Casual_Lapel_{side}",
            Vector((
                chest.x + sign * sw * 0.225,
                lapel_y,
                lapel_z,
            )),
            (lapel_w, lapel_d, lapel_h),
            black,
            coll,
            armature,
            "Chest",
            rotation=(0.0, 0.0, math.radians(sign * 18)),
            bevel=max(sw * 0.008, 0.003),
        )

    # One fitted thigh strap mirrors the reference without adding bulky geometry.
    strap_leg = "UpperLeg_R"
    strap_pos = bone_head(armature, strap_leg).lerp(
        bone_tail(armature, strap_leg),
        0.22,
    )
    add_torus(
        "Casual_ThighStrap_R",
        strap_pos,
        max(hw * 0.17, 0.045),
        max(hw * 0.014, 0.004),
        black,
        coll,
        armature,
        strap_leg,
    )

def build_cafe_maid(armature, coll, m):
    cream = material("Cream", "cream", roughness=0.56)
    white = material("White", "white", roughness=0.5)
    black = material("Black", "black", roughness=0.40)
    amber = material("Amber", "honey_amber", metallic=0.12, roughness=0.36)
    hips, chest, neck = m["hips"], m["chest"], m["neck"]
    sw, hw, depth, th = m["shoulder_width"], m["hip_width"], m["depth"], m["torso_height"]

    add_box("Maid_Bodice", chest, (sw * 0.70, depth * 1.0, th * 0.52),
            cream, coll, armature, "Chest", bevel=0.03)
    add_box("Maid_WaistCorset", hips + Vector((0, 0, th * 0.13)),
            (hw * 0.96, depth * 1.04, th * 0.18), black, coll, armature, "Hips", bevel=0.025)
    add_cone("Maid_SkirtBlack", hips + Vector((0, 0, -th * 0.26)),
             hw * 0.55, hw * 1.00, th * 0.52, black, coll, armature)
    add_cone("Maid_SkirtCream", hips + Vector((0, 0, -th * 0.22)),
             hw * 0.48, hw * 0.83, th * 0.44, cream, coll, armature)
    add_box("Maid_ApronFront", hips + Vector((0, -depth * 0.42, -th * 0.18)),
            (hw * 0.72, depth * 0.08, th * 0.50), white, coll, armature, "Hips", bevel=0.018)
    for side, upper in (("L", "UpperArm_L"), ("R", "UpperArm_R")):
        pos = bone_head(armature, upper).lerp(bone_tail(armature, upper), 0.22)
        add_sphere(f"Maid_PuffSleeve_{side}", pos,
                   (sw * 0.13, sw * 0.13, sw * 0.13),
                   cream, coll, armature, upper)
    add_bow("Maid_NeckBow", neck + Vector((0, -depth * 0.30, -th * 0.05)),
            sw * 0.13, black, coll, armature, "Chest")
    add_torus("Maid_WaistAccent", hips + Vector((0, 0, th * 0.13)),
              hw * 0.56, hw * 0.022, amber, coll, armature, "Hips")
    add_socks("Maid", armature, coll, white, tall=False)
    add_basic_shoes("Maid", armature, coll, black, chunky=False)

def build_sporty(armature, coll, m):
    white = material("White", "white", roughness=0.48)
    black = material("Black", "black", roughness=0.34)
    amber = material("Amber", "honey_amber", metallic=0.08, roughness=0.32)
    hips, chest, head = m["hips"], m["chest"], m["head"]
    sw, hw, depth, th = m["shoulder_width"], m["hip_width"], m["depth"], m["torso_height"]

    add_box("Sporty_CropTop", chest + Vector((0, 0, -th * 0.05)),
            (sw * 0.65, depth * 0.98, th * 0.28), white, coll, armature, "Chest", bevel=0.035)
    add_box("Sporty_CroppedJacket", chest + Vector((0, 0, th * 0.12)),
            (sw * 1.10, depth * 1.20, th * 0.26), black, coll, armature, "Chest", bevel=0.045)
    add_arm_sleeves("Sporty_Jacket", armature, coll, black, oversized=True)
    add_box("Sporty_Shorts", hips + Vector((0, 0, -th * 0.10)),
            (hw * 1.18, depth * 1.12, th * 0.25), black, coll, armature, "Hips", bevel=0.025)
    add_torus("Sporty_WaistCord", hips + Vector((0, 0, th * 0.02)),
              hw * 0.60, hw * 0.020, amber, coll, armature, "Hips")
    add_sphere("Sporty_Cap", head + Vector((0, 0, th * 0.18)),
               (sw * 0.30, sw * 0.31, sw * 0.16),
               black, coll, armature, "Head")
    add_box("Sporty_CapBrim", head + Vector((0, -sw * 0.24, th * 0.11)),
            (sw * 0.36, sw * 0.24, sw * 0.035), black, coll, armature, "Head", bevel=0.018)
    add_torus("Sporty_Headphones", m["neck"] + Vector((0, 0, th * 0.07)),
              sw * 0.30, sw * 0.045, black, coll, armature, "Neck",
              rotation=(math.radians(90), 0, 0))
    add_socks("Sporty", armature, coll, white, tall=False)
    add_basic_shoes("Sporty", armature, coll, black, chunky=True)

def build_elegant_evening(armature, coll, m):
    black = material("Black", "black", roughness=0.28)
    brown = material("SoftBrown", "soft_brown", roughness=0.40)
    amber = material("Amber", "honey_amber", metallic=0.35, roughness=0.24)
    cream = material("Cream", "cream", roughness=0.5)
    hips, chest, neck = m["hips"], m["chest"], m["neck"]
    sw, hw, depth, th = m["shoulder_width"], m["hip_width"], m["depth"], m["torso_height"]

    add_box("Evening_Corset", chest + Vector((0, 0, -th * 0.07)),
            (sw * 0.68, depth * 0.95, th * 0.52), black, coll, armature, "Chest", bevel=0.03)
    add_box("Evening_CorsetAccent", chest + Vector((0, -depth * 0.46, -th * 0.07)),
            (sw * 0.12, depth * 0.08, th * 0.45), amber, coll, armature, "Chest", bevel=0.012)
    add_cone("Evening_LongSkirt", hips + Vector((0, 0, -th * 0.72)),
             hw * 0.55, hw * 1.28, th * 1.45, brown, coll, armature)
    add_cone("Evening_InnerSkirt", hips + Vector((0, -depth * 0.08, -th * 0.68)),
             hw * 0.42, hw * 0.90, th * 1.30, cream, coll, armature)
    add_arm_sleeves("Evening_Sleeve", armature, coll, brown, oversized=True)
    add_torus("Evening_Choker", neck, sw * 0.20, sw * 0.025,
              black, coll, armature, "Neck")
    add_basic_shoes("Evening", armature, coll, black, chunky=False, heels=True)

def build_cozy_sweater(armature, coll, m):
    cream = material("Cream", "cream", roughness=0.78)
    brown = material("SoftBrown", "soft_brown", roughness=0.58)
    amber = material("Amber", "honey_amber", roughness=0.44)
    hips, chest = m["hips"], m["chest"]
    sw, hw, depth, th = m["shoulder_width"], m["hip_width"], m["depth"], m["torso_height"]

    add_box("Cozy_OversizedSweater", chest + Vector((0, 0, -th * 0.12)),
            (sw * 1.14, depth * 1.42, th * 0.92), cream, coll, armature, "Chest", bevel=0.075)
    add_arm_sleeves("Cozy_Sleeve", armature, coll, cream, oversized=True)
    add_box("Cozy_KnitShorts", hips + Vector((0, 0, -th * 0.10)),
            (hw * 1.05, depth * 1.05, th * 0.22), brown, coll, armature, "Hips", bevel=0.035)
    add_socks("Cozy", armature, coll, cream, tall=True)
    add_basic_shoes("Cozy", armature, coll, cream, chunky=True)
    for side, foot in (("L", "Foot_L"), ("R", "Foot_R")):
        add_bow(f"Cozy_SlipperBow_{side}",
                bone_center(armature, foot) + Vector((0, -0.08, 0.07)),
                sw * 0.07, amber, coll, armature, foot)

def build_techwear(armature, coll, m):
    white = material("White", "white", roughness=0.42)
    black = material("Black", "black", roughness=0.32)
    amber = material("Amber", "honey_amber", metallic=0.35, roughness=0.24)
    hips, chest, neck = m["hips"], m["chest"], m["neck"]
    sw, hw, depth, th = m["shoulder_width"], m["hip_width"], m["depth"], m["torso_height"]

    add_box("Techwear_Bodice", chest,
            (sw * 0.72, depth * 0.98, th * 0.52), white, coll, armature, "Chest", bevel=0.028)
    add_box("Techwear_Harness", chest + Vector((0, -depth * 0.48, 0)),
            (sw * 0.10, depth * 0.07, th * 0.62), black, coll, armature, "Chest",
            rotation=(0, 0, math.radians(20)), bevel=0.01)
    add_box("Techwear_Harness2", chest + Vector((0, -depth * 0.48, 0)),
            (sw * 0.10, depth * 0.07, th * 0.62), black, coll, armature, "Chest",
            rotation=(0, 0, math.radians(-20)), bevel=0.01)
    add_cone("Techwear_Skirt", hips + Vector((0, 0, -th * 0.24)),
             hw * 0.52, hw * 0.86, th * 0.45, black, coll, armature)
    for index, angle in enumerate((-55, -28, 0, 28, 55)):
        rad = math.radians(angle)
        offset = Vector((math.sin(rad) * hw * 0.52, 0, -th * 0.38))
        add_box(
            f"Techwear_Panel_{index}",
            hips + offset,
            (hw * 0.18, depth * 0.16, th * 0.55),
            amber if index % 2 == 0 else white,
            coll, armature, "Hips",
            rotation=(0, 0, -rad * 0.45),
            bevel=0.012,
        )
    add_arm_sleeves("Techwear_Arm", armature, coll, black, oversized=False, short=True)
    for side in ("L", "R"):
        hand = f"Hand_{side}"
        add_sphere(f"Techwear_Glove_{side}",
                   bone_center(armature, hand),
                   (sw * 0.075, sw * 0.055, sw * 0.10),
                   black, coll, armature, hand)
    add_torus("Techwear_Collar", neck, sw * 0.22, sw * 0.025,
              black, coll, armature, "Neck")
    add_basic_shoes("Techwear", armature, coll, black, chunky=True)

def build_preset(preset, armature, collection):
    m = metrics(armature)
    builders = {
        "casual-streetwear": build_casual_streetwear,
        "cafe-maid": build_cafe_maid,
        "sporty-athleisure": build_sporty,
        "elegant-evening": build_elegant_evening,
        "cozy-sweater": build_cozy_sweater,
        "futuristic-idol-techwear": build_techwear,
    }
    builders[preset](armature, collection, m)

def try_export_vrm(filepath):
    if not filepath:
        return False
    export_scene = getattr(bpy.ops, "export_scene", None)
    operator = getattr(export_scene, "vrm", None) if export_scene else None
    if operator is None:
        print("[Sarah outfits] VRM exporter is not installed; saved .blend only.")
        return False
    try:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        operator(filepath=str(Path(filepath).resolve()))
        print(f"[Sarah outfits] Exported VRM: {filepath}")
        return True
    except Exception as exc:
        print(f"[Sarah outfits] VRM export failed ({type(exc).__name__}): {exc}")
        return False

def main():
    args = parse_args()
    armature = find_armature()
    hide_original_costume()

    name = f"Sarah_Outfit_{args.preset.replace('-', '_')}"
    existing = bpy.data.collections.get(name)
    if existing:
        for obj in list(existing.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(existing)

    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    collection["sarah_outfit_preset"] = args.preset

    build_preset(args.preset, armature, collection)

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    print(f"[Sarah outfits] Saved Blender variant: {output}")

    if args.vrm_output:
        try_export_vrm(args.vrm_output)

if __name__ == "__main__":
    main()
