import bpy

from bpy.props import PointerProperty, BoolProperty
from bpy.types import Node
from .._base.node_base import ScNode
from .._base.node_input import ScInputNode
from ...helper import focus_on_object, remove_object, sc_poll_mesh, apply_all_modifiers

def poll_object(self, object):
    if self.in_mesh_only:
        return sc_poll_mesh(self, object)
    return True

class ScCustomObject(Node, ScInputNode):
    bl_idname = "ScCustomObject"
    bl_label = "Custom Object"

    in_obj: PointerProperty(type=bpy.types.Object, poll=poll_object, update=ScNode.update_value)
    in_hide: BoolProperty(default=True, update=ScNode.update_value)
    in_mesh_only: BoolProperty(default=True, update=ScNode.update_value)
    in_hierarchy: BoolProperty(default=False, update=ScNode.update_value)
    
    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketObject", "Object").init("in_obj", True)
        self.inputs.new("ScNodeSocketBool", "Hide Original").init("in_hide")
        self.inputs.new("ScNodeSocketBool", "Mesh Only").init("in_mesh_only")
        self.inputs.new("ScNodeSocketBool", "Copy Hierarchy").init("in_hierarchy")
     
    def error_condition(self):
        return (
            super().error_condition()
            or self.inputs["Object"].default_value == None
        )
    
    def pre_execute(self):
        self.inputs["Object"].default_value.hide_set(False)
        focus_on_object(self.inputs["Object"].default_value)

    def functionality(self):
        if self.inputs["Copy Hierarchy"].default_value:
            bpy.ops.object.select_grouped(extend=True, type='CHILDREN_RECURSIVE')
        bpy.ops.object.duplicate()
        bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    
    def post_execute(self):
        out = super().post_execute()
        apply_all_modifiers(self.out_mesh)
        self.inputs["Object"].default_value.hide_set(self.inputs["Hide Original"].default_value)
        return out
    
    def free(self):
        super().free()
        if (self.inputs["Object"].default_value):
            self.inputs["Object"].default_value.hide_set(False)