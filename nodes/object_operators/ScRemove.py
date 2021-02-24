import bpy

from bpy.props import BoolProperty, PointerProperty
from bpy.types import Node
from .._base.node_base import ScNode
from .._base.node_operator import ScObjectOperatorNode
from ...helper import remove_object, print_log

class ScRemove(Node, ScObjectOperatorNode):
    bl_idname = "ScRemove"
    bl_label = "Remove"

    in_target_obj: PointerProperty(type=bpy.types.Object, update=ScNode.update_value)
    in_hierarchy: BoolProperty(default=False, update=ScNode.update_value)

    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketObject", "Target").init("in_target_obj", True)
        self.inputs.new("ScNodeSocketBool", "Remove Hierarchy").init("in_hierarchy")
    
    def error_condition(self):
        return(
            super().error_condition()
            or self.inputs["Target"].default_value == None
        )
    
    def functionality(self):
        remove_object(self.inputs["Target"].default_value, hierarchy=self.inputs["Remove Hierarchy"].default_value)
        #bpy.data.objects.remove(self.inputs["Target"].default_value, do_unlink=True)
        #! SED: Better than selection semantics?
        # bpy.ops.object.delete()
