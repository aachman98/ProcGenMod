import bpy

from bpy.props import FloatProperty, BoolProperty
from bpy.types import Node
from .._base.node_base import ScNode
from .._base.node_input import ScInputNode

class ScCube(Node, ScInputNode):
    bl_idname = "ScCube"
    bl_label = "Cube"
    
    in_uv: BoolProperty(default=True, update=ScNode.update_value)
    in_size: FloatProperty(default=2.0, min=0.0, update=ScNode.update_value)
    in_WorldOrigin: BoolProperty(default=False, update=ScNode.update_value)#默认世界原点为否 World Origin default=False

    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketBool", "Generate UVs").init("in_uv")
        self.inputs.new("ScNodeSocketNumber", "Size").init("in_size", True)
        self.inputs.new("ScNodeSocketBool", "World Origin").init("in_WorldOrigin",True)#默认原点原点为否，在节点显示 display in node
    
    def error_condition(self):
        return (
            super().error_condition()
            or self.inputs["Size"].default_value <= 0
        )
    #是否是在原点创建物体,不是默认则在游标创建物体 Whether the object is created at the origin, not at the cursor by default
    def functionality(self):
        if (self.inputs["World Origin"].default_value):
            bpy.ops.mesh.primitive_cube_add(
                size = self.inputs["Size"].default_value,
                calc_uvs = self.inputs["Generate UVs"].default_value,
                align='WORLD',
                location=(0.0, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0)
            )
        else:
            bpy.ops.mesh.primitive_cube_add(
                size = self.inputs["Size"].default_value,
                calc_uvs = self.inputs["Generate UVs"].default_value,
            )
