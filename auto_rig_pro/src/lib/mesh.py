import bpy, bmesh
from .objects import *
from .bone_data import *
from .version import *

def overwrite_vgroup(obj, vgroup, new_vgname):
    new_vgrp = obj.vertex_groups.get(new_vgname)                    
    if new_vgrp:
        obj.vertex_groups.remove(new_vgrp)
    vgroup.name = new_vgname


def create_mesh_data(mesh_name, verts, edges, faces):
    # create an new mesh data given verts, edges and faces data
    new_mesh = bpy.data.meshes.new(name=mesh_name)
    new_mesh.from_pydata(verts, edges, faces)
    return new_mesh


def create_object_mesh(obj_name, verts, edges, faces):
    shape_mesh = create_mesh_data(obj_name, verts, edges, faces)
    # create object
    shape = bpy.data.objects.new(obj_name, shape_mesh)
    return shape


def transfer_shape_keys_deformed(source_obj, target_obj, apply_mods=False):  
    if source_obj == None or target_obj == None:
        return

    # disable all non-armature modifiers to solve issues when baking the mesh
    disabled_mod = {}
    if apply_mods == False:
        for obj in [source_obj, target_obj]:
            for mod in obj.modifiers:                
                if mod.type != "ARMATURE" and mod.show_viewport:           
                    mod.show_viewport = False
                    if not obj.name in disabled_mod:
                        disabled_mod[obj.name] = {}
                    disabled_mod[obj.name][mod.name] = mod.name
                    
    if apply_mods:
        # enable viewport modifier level if render is enabled
        # necessary to bake mesh properly
        for mod in source_obj.modifiers:
            if mod.show_render:
                mod.show_viewport = True  
                
    if source_obj.data.shape_keys == None:
        return

    source_shape_keys = source_obj.data.shape_keys.key_blocks

    basis_index = 0
    # get the Basis shape key index
    for sk_index, sk in enumerate(source_shape_keys):
        if "Basis" in source_shape_keys[sk_index].name:
            basis_index = sk_index
            # pin the Basis key
            source_obj.active_shape_key_index = basis_index
            source_obj.show_only_shape_key = True
            bpy.context.evaluated_depsgraph_get().update()
            break

    # store the vert coords in basis shape keys
    mesh_baked = bmesh.new()    
    if bpy.app.version < (2,93,0):
        mesh_baked.from_object(source_obj, bpy.context.evaluated_depsgraph_get(), deform=True, face_normals=False)
    elif bpy.app.version >= (2,93,0) and bpy.app.version < (3,0,2):
        mesh_baked.from_object(source_obj, bpy.context.evaluated_depsgraph_get(), face_normals=False)
    elif bpy.app.version >= (3,0,2):
        mesh_baked.from_object(source_obj, bpy.context.evaluated_depsgraph_get())#, cage=False, face_normals=False, vertex_normals=False)
        
    mesh_baked.verts.ensure_lookup_table()
    base_verts_coords = [i.co for i in mesh_baked.verts]
    
    if 'mesh_baked' in locals():
        del mesh_baked

    # store the vert coords in basis shape keys
    for sk_index, sk in enumerate(source_shape_keys):
        if sk_index == basis_index:
            continue

        source_obj.active_shape_key_index = sk_index
        bpy.context.evaluated_depsgraph_get().update()

        # get the verts moved in shape key
        mesh_baked1 = bmesh.new()
        if bpy.app.version < (2,93,0):
            mesh_baked1.from_object(source_obj, bpy.context.evaluated_depsgraph_get(), deform=True, face_normals=False)
        elif bpy.app.version >= (2,93,0) and bpy.app.version < (3,0,2):
            mesh_baked1.from_object(source_obj, bpy.context.evaluated_depsgraph_get(), face_normals=False)
        elif bpy.app.version >= (3,0,2):
            mesh_baked1.from_object(source_obj, bpy.context.evaluated_depsgraph_get())#, cage=False, face_normals=False, vertex_normals=False)
        
        mesh_baked1.verts.ensure_lookup_table()        
        
        if len(mesh_baked1.verts) == len(base_verts_coords):       
            deformed_verts_coords = [i.co for i in mesh_baked1.verts]           
            deformed_verts_index_list = []

            for vert_index, vert in enumerate(mesh_baked1.verts):
                if vert.co != base_verts_coords[vert_index]:
                    deformed_verts_index_list.append(vert_index)
                
            # transfer the shape key
            #bpy.ops.object.shape_key_transfer()
            create_basis = False
            if target_obj.data.shape_keys == None:
                create_basis = True    
            elif len(target_obj.data.shape_keys.key_blocks) == 0:
                create_basis = True
            if create_basis:# add basis
                target_obj.shape_key_add(name='Basis')
                
            target_sk = target_obj.shape_key_add(name=sk.name)
            target_sk.value = sk.value
            target_sk.slider_min, target_sk.slider_max = sk.slider_min, sk.slider_max
            #target_sk = target_obj.data.shape_keys.key_blocks[sk_index]       
           
            # correct the deformed vert coordinates
            for deformed_vert_index in deformed_verts_index_list:
                #print("set vertex", deformed_vert_index, "from", target_sk.data[deformed_vert_index].co, "TO", mesh_baked1.verts[deformed_vert_index].co)
                target_sk.data[deformed_vert_index].co = mesh_baked1.verts[deformed_vert_index].co
                
        else:# looks like a modifier is adding or removing verts from one shape key to another... not supported! (e.g Bevel, angle based, Decimate...)
            print('Cannot transfer shape key, different amount of vertices. ShapeKey:', sk.name, 'Object:', source_obj.name, '> Aborting')
            
        if 'mesh_baked1' in locals():
            del mesh_baked1

    source_obj.show_only_shape_key = False
    target_obj.show_only_shape_key = False

    # copy drivers
    anim_data = source_obj.data.shape_keys.animation_data

    if anim_data and anim_data.drivers:
        if target_obj.data.shape_keys:# If None, shape keys couldn't transfer previously, invalid modifier
            obj_anim_data = target_obj.data.shape_keys.animation_data_create()

            for fcurve in anim_data.drivers:
                new_fc = obj_anim_data.drivers.from_existing(src_driver=fcurve)
                new_fc.driver.is_valid = True

                for dvar in new_fc.driver.variables:
                    for dtar in dvar.targets:
                        if dtar.id == source_obj:
                            dtar.id = target_obj

    # restore disabled modifiers  
    for objname in disabled_mod:
        ob = get_object(objname)
        for modname in disabled_mod[objname]:         
            ob.modifiers[modname].show_viewport = True
            

# Transfer weights with operators. Slower or faster than per vertex depending on the context
def transfer_weight_mod_operator(object=None, src_grp_name=None, tar_grp_name=None, replace=False):

    mix_mod = object.modifiers.new(type='VERTEX_WEIGHT_MIX', name='ARP_VWM')
    mix_mod.vertex_group_a = tar_grp_name
    mix_mod.vertex_group_b = src_grp_name
    mix_mod.mix_set = 'ALL'
    if replace:
        mix_mod.mix_mode = 'SET'
    else:
        mix_mod.mix_mode = 'ADD'
        
    # set in first position
    i_test = 0# safety check, some modifiers can't be moved, limit maximum trials
    while object.modifiers[0] != mix_mod and i_test < 50:
        i_test += 1
        bpy.ops.object.modifier_move_up(modifier="ARP_VWM")
    
    bpy.ops.object.modifier_apply(modifier='ARP_VWM')   
    
    
def transfer_weight_mod(object=None, dict=None, list=None, replace=False, tar_grp_name=""):
       
    #vgroups_copy = [i for i in object.vertex_groups]
    vgroups_names_copy = [i.name for i in object.vertex_groups]
    
    for vgroup_name in vgroups_names_copy:
        v_group = object.vertex_groups.get(vgroup_name)
        
        grp_name_base = get_bone_base_name(v_group.name)
        side = get_bone_side(v_group.name)
        
        if dict:
            if grp_name_base in dict:
                for tar_grp_base_name in dict[grp_name_base]:
                    if tar_grp_base_name.endswith('.x'):
                        side = side[:-2]
                    
                    tar_grp_name = tar_grp_base_name+side                  
                    if object.vertex_groups.get(tar_grp_name) == None:
                        object.vertex_groups.new(name=tar_grp_name)
                    
                    transfer_weight_mod_operator(object=object, src_grp_name=v_group.name, tar_grp_name=tar_grp_name, replace=replace)
                    
        if list:
            if grp_name_base in list:                
                if object.vertex_groups.get(tar_grp_name) == None:
                    object.vertex_groups.new(name=tar_grp_name)                    
                    
                transfer_weight_mod_operator(object=object, src_grp_name=v_group.name, tar_grp_name=tar_grp_name, replace=replace)
        
        
def transfer_weight_prefix_mod(object=None, prefix=None, tar_grp_base_name=None):
    
    vgroups_names_copy = [i.name for i in object.vertex_groups]# iterating over a copy fix bug: UnicodeDecodeError: 'utf-8' codec can't decode byte 0xb0 in position 1: invalid start byte
    
    for vgr_n in vgroups_names_copy:
        vgr = object.vertex_groups.get(vgr_n)
        
        if vgr.index == -1:            
            continue
        
        if vgr.name.startswith(prefix):
            side = vgr.name[-2:]
            tar_grp_name = tar_grp_base_name+side
            
            if object.vertex_groups.get(tar_grp_name):#if exists
                transfer_weight_mod_operator(object=object, src_grp_name=vgr.name, tar_grp_name=tar_grp_name)
                
                
def clamp_weight_mod(object=None, dict=None, list=None):
    
    for vg in object.vertex_groups:
        grp_name_base = get_bone_base_name(vg.name)
        side = get_bone_side(vg.name)
        
        if dict:
            if grp_name_base in dict:
                tar_grp_base_name = dict[grp_name_base]
                
                if tar_grp_base_name.endswith('.x'):
                    side = side[:-2]
                
                tar_grp_name = tar_grp_base_name+side
                tar_grp = object.vertex_groups.get(tar_grp_name)
                
                if tar_grp:
                    clamp_weight_mod_operator(object=object, src_grp_name=vg.name, tar_grp_name=tar_grp_name)
                    
                
def clamp_weight_mod_operator(object=None, src_grp_name=None, tar_grp_name=None):

    mix_mod = object.modifiers.new(type='VERTEX_WEIGHT_MIX', name='ARP_VWM')
    mix_mod.vertex_group_a = tar_grp_name
    mix_mod.vertex_group_b = src_grp_name
    mix_mod.mix_set = 'A'
    mix_mod.mix_mode = 'SET'
        
    # set in first position
    i_test = 0# safety check, some modifiers can't be moved
    while object.modifiers[0] != mix_mod and i_test < 50:
        i_test += 1
        bpy.ops.object.modifier_move_up(modifier="ARP_VWM")
    
    # apply
    bpy.ops.object.modifier_apply(modifier='ARP_VWM')
    
 
def multiply_weight_mod_operator(object=None, tar_grp_name='', fac=0.5):
    
    mix_mod = object.modifiers.new(type='VERTEX_WEIGHT_MIX', name='ARP_VWM')
    mix_mod.vertex_group_a = tar_grp_name
    mix_mod.mix_set = 'ALL'
    mix_mod.mix_mode = 'SET'
    mix_mod.mask_constant = 1 - fac
    
    # set in first position
    i_test = 0# safety check, some modifiers can't be moved
    while object.modifiers[0] != mix_mod and i_test < 50:
        i_test += 1
        bpy.ops.object.modifier_move_up(modifier="ARP_VWM")
    
    # apply
    bpy.ops.object.modifier_apply(modifier='ARP_VWM')

 
def multiply_weight_mod(object=None, dict=None):  
    
    for _vg in object.vertex_groups:    
        grp_name_base = get_bone_base_name(_vg.name)
        side = get_bone_side(_vg.name)
        
        if grp_name_base in dict:
            fac = dict[grp_name_base]
            multiply_weight_mod_operator(object=object, tar_grp_name=_vg.name, fac=fac)         
            

# Transfer weights functions per vertex. Slower or faster than operator depending on the context       
def transfer_weight(object=None, vertice=None, vertex_weight=None, group_name=None, dict=None, list=None, target_group_name=None):    
    grp_name_base = get_bone_base_name(group_name)
    side = get_bone_side(group_name)

    # Dict mode
    if dict:
        if grp_name_base in dict:
            for target_grp in dict[grp_name_base]:
                if target_grp.endswith('.x'):
                    side = side[:-2]

                target_group_name = target_grp + side
                target_group = object.vertex_groups.get(target_group_name)
                if target_group == None:
                    target_group = object.vertex_groups.new(name=target_group_name)

                target_group.add([vertice.index], vertex_weight, 'ADD')

    # List mode
    if list:
        if grp_name_base in list:
            target_group = object.vertex_groups.get(target_group_name)
            if target_group == None:
                target_group = object.vertex_groups.new(name=target_group_name)
                
            target_group.add([vertice.index], vertex_weight, 'ADD')


def transfer_weight_prefix(object=None, vertice=None, vertex_weight=None, group_name=None, prefix=None, target_group=None):
    if group_name.startswith(prefix):
        side = group_name[-2:]
        tar_group_name = target_group+side
        if object.vertex_groups.get(tar_group_name):# if exists
            object.vertex_groups[tar_group_name].add([vertice.index], vertex_weight, 'ADD')

       
def copy_weight(object=None, vertice=None, vertex_weight=None, group_name=None, dict=None):
    side = get_bone_side(group_name)
    grp_name_base = get_bone_base_name(group_name)

    if grp_name_base in dict:
        if dict[grp_name_base][-2:] == '.x':
            side = side[:-2]

        for target_grp in dict[grp_name_base]:
            _target_group = target_grp + side

            if object.vertex_groups.get(_target_group) == None:
                object.vertex_groups.new(name=_target_group)

            object.vertex_groups[_target_group].add([vertice.index], vertex_weight, 'REPLACE')
            
            
def multiply_weight(object=None, vertice=None, vertex_weight=None, group_name=None, dict=None):
    grp_name_base = get_bone_base_name(group_name)
    side = get_bone_side(group_name)

    if grp_name_base in dict:
        if object.vertex_groups.get(group_name) != None:#if exists
            object.vertex_groups[group_name].add([vertice.index], vertex_weight * dict[grp_name_base], 'REPLACE')
            
            
def clamp_weights(object=None, vertice=None, vertex_weight=None, group_name=None, dict=None):

    grp_name_base = group_name[:-2]
    side = group_name[-2:]

    if "_dupli_" in group_name:
        grp_name_base = group_name[:-12]
        side = "_" + group_name[-11:]

    if grp_name_base in dict:
        if dict[grp_name_base][-2:] == '.x':
            side = ''

        _target_group = dict[grp_name_base]+side
        target_weight = 0.0

        if object.vertex_groups.get(_target_group) != None:
            for grp in vertice.groups:
                if object.vertex_groups[grp.group].name == _target_group:
                    target_weight = grp.weight

        def_weight = min(vertex_weight, target_weight)
        object.vertex_groups[group_name].add([vertice.index], def_weight, 'REPLACE')