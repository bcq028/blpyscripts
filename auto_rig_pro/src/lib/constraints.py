import bpy
from .bone_pose import *
from mathutils import *
from math import *


def set_constraint_inverse_matrix(cns):
    # set the inverse matrix of Child Of constraint
    subtarget_pbone = get_pose_bone(cns.subtarget)
    if subtarget_pbone:
        cns.inverse_matrix = subtarget_pbone.bone.matrix_local.to_4x4().inverted()


def add_copy_transf(p_bone, tar=None, subtar="", h_t=0.0, no_scale=False):
    if tar == None:
        tar = bpy.context.active_object

    if no_scale:
        cns1 = p_bone.constraints.new("COPY_LOCATION")
        cns1.name = "Copy Location"
        cns1.target = tar
        cns1.subtarget = subtar
        cns1.head_tail = h_t

        cns2 = p_bone.constraints.new("COPY_ROTATION")
        cns2.name = "Copy Rotation"
        cns2.target = tar
        cns2.subtarget = subtar

        return cns1, cns2
    else:
        cns1 = p_bone.constraints.new("COPY_TRANSFORMS")
        cns1.name = "Copy Transforms"
        cns1.target = tar
        cns1.subtarget = subtar
        cns1.head_tail=h_t

        return cns1, None
        
        
def get_constraint_index(pb, cns):
    for i, c in enumerate(pb.constraints):
        if c == cns:
            return i        

        
def move_constraint(pbone, cns, dir, repeat):
    # must be in pose mode
    
    # the bone layer must be enabled
    enabled_layers = []
    armature = bpy.context.active_object

    for i, lay in enumerate(pbone.bone.layers):
        if lay and armature.data.layers[i] == False:
            armature.data.layers[i] = True
            enabled_layers.append(i)
 
    # move
    if bpy.app.version >= (2, 81, 16):        
        cns_idx = get_constraint_index(pbone, cns)
        to_idx = cns_idx+repeat if dir == 'DOWN' else cns_idx-repeat 
        if to_idx > len(pbone.constraints)-1:
            to_idx = len(pbone.constraints)-1
        if to_idx < 0:
            to_idx = 0
        pbone.constraints.move(cns_idx, to_idx)
        
    else:# backward-compatibility
        bpy.context.active_object.data.bones.active = pbone.bone
        my_context = bpy.context.copy()
        my_context["constraint"] = cns

        for i in range(0, repeat):
            if dir == 'UP':
                bpy.ops.constraint.move_up(my_context, constraint=cns.name, owner='BONE')
            elif dir == 'DOWN':
                bpy.ops.constraint.move_down(my_context, constraint=cns.name, owner='BONE')

    # restore layers
    for idx in enabled_layers:
        armature.data.layers[idx] = False