import bpy

from bpy.props import FloatProperty
from bpy.types import Node
from .._base.node_base import ScNode
from .._base.node_operator import ScEditOperatorNode

class ScEdgeCrease(Node, ScEditOperatorNode):
    bl_idname = "ScEdgeCrease"
    bl_label = "Edge Crease"

    in_value: FloatProperty(update=ScNode.update_value)

    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketNumber", "Value").init("in_value", True)
    
    def error_condition(self):
        return(
            super().error_condition()
        )
    
    def functionality(self):
        bpy.ops.transform.edge_crease(value=self.inputs["Value"].default_value)
