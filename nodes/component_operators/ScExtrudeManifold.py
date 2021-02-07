import bpy

from bpy.props import BoolProperty, FloatVectorProperty
from bpy.types import Node
from .._base.node_base import ScNode
from .._base.node_operator import ScEditOperatorNode
from ...helper import get_override

class ScExtrudeManifold(Node, ScEditOperatorNode):
    bl_idname = "ScExtrudeManifold"
    bl_label = "ExtrudeManifold"
    
    in_value: FloatVectorProperty(update=ScNode.update_value)
    in_use_normal_flip: BoolProperty(update=ScNode.update_value)
    in_use_dissolve_ortho_edges: BoolProperty(update=ScNode.update_value,default=True)
    in_use_automerge_and_split: BoolProperty(update=ScNode.update_value,default=True)
    in_mirror: BoolProperty(update=ScNode.update_value)
    
    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketVector", "Value").init("in_value", True)
        self.inputs.new("ScNodeSocketBool", "Flip Normals").init("in_use_normal_flip")
        self.inputs.new("ScNodeSocketBool", "Dissolve Ortho Edges").init("in_use_dissolve_ortho_edges")
        self.inputs.new("ScNodeSocketBool", "Use Automerge and Split").init("in_use_automerge_and_split")
        self.inputs.new("ScNodeSocketBool", "Mirror Editing").init("in_mirror")
    
    def functionality(self):
        bpy.ops.mesh.extrude_manifold(
            get_override(self.inputs["Object"].default_value, True),
            MESH_OT_extrude_region = {
                "use_normal_flip": self.inputs["Flip Normals"].default_value,
                "use_dissolve_ortho_edges": self.inputs["Dissolve Ortho Edges"].default_value,
                "mirror": self.inputs["Mirror Editing"].default_value
            },
            TRANSFORM_OT_translate = {
                "value": self.inputs["Value"].default_value,
                "use_automerge_and_split": self.inputs["Use Automerge and Split"].default_value
            }
        )