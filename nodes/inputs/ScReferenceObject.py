import bpy

from bpy.props import PointerProperty
from bpy.types import Node
from .._base.node_base import ScNode
from .._base.node_reference import ScReferenceNode
from ...helper import focus_on_object

class ScReferenceObject(Node, ScReferenceNode):
    bl_idname = "ScReferenceObject"
    bl_label = "Reference Object"

    in_obj: PointerProperty(type=bpy.types.Object, update=ScNode.update_value)
    
    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketObject", "Object").init("in_obj", True)
     
    def error_condition(self):
        return (
            super().error_condition()
            or self.inputs["Object"].default_value == None
        )
    
    def pre_execute(self):
        focus_on_object(self.inputs["Object"].default_value)
