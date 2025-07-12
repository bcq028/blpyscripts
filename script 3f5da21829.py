import bpy

D = bpy.data
C = bpy.context
ops = bpy.ops


for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
         armature:bpy.types.Armature = obj.data
         for bone in armature.bones:
              print(bone.name)