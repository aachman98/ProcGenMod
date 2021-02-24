import bpy

from bpy.props import PointerProperty, StringProperty, BoolProperty
from .._base.node_base import ScNode
from ...helper import focus_on_object, remove_object

class ScReferenceNode(ScNode):
    in_name: StringProperty(default="Object", update=ScNode.update_value)
    out_mesh: PointerProperty(type=bpy.types.Object)

    def init(self, context):
        self.node_executable = True
        super().init(context)
        self.inputs.new("ScNodeSocketString", "Name").init("in_name")
        self.outputs.new("ScNodeSocketObject", "Object")
    
    def error_condition(self):
        return (
            self.inputs["Name"].default_value == ""
        )
    
    def pre_execute(self):
        if (bpy.ops.object.mode_set.poll()):
            bpy.ops.object.mode_set(mode="OBJECT")
    
    def post_execute(self):
        out = {}
        self.out_mesh = bpy.context.active_object
        out["Object"] = self.out_mesh
        return out
    
    def free(self):
        pass
    