import bpy

from bpy.props import IntProperty, FloatProperty, BoolProperty
from bpy.types import Node
from .._base.node_base import ScNode
from .._base.node_input import ScInputNode

class ScGrid(Node, ScInputNode):
    bl_idname = "ScGrid"
    bl_label = "Grid"

    in_uv: BoolProperty(default=True, update=ScNode.update_value)
    in_x: IntProperty(default=10, min=2, max=10000000, update=ScNode.update_value)
    in_y: IntProperty(default=10, min=2, max=10000000, update=ScNode.update_value)
    in_size: FloatProperty(default=2.0, min=0.0, update=ScNode.update_value)
    in_WorldOrigin: BoolProperty(default=False, update=ScNode.update_value)

    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketBool", "Generate UVs").init("in_uv")
        self.inputs.new("ScNodeSocketNumber", "X Subdivisions").init("in_x", True)
        self.inputs.new("ScNodeSocketNumber", "Y Subdivisions").init("in_y", True)
        self.inputs.new("ScNodeSocketNumber", "Size").init("in_size", True)
        self.inputs.new("ScNodeSocketBool", "World Origin").init("in_WorldOrigin",True)
    
    def error_condition(self):
        return (
            super().error_condition()
            or (self.inputs["X Subdivisions"].default_value < 2 or self.inputs["X Subdivisions"].default_value > 10000000)
            or (self.inputs["Y Subdivisions"].default_value < 2 or self.inputs["Y Subdivisions"].default_value > 10000000)
            or self.inputs["Size"].default_value <= 0
        )
    
    def functionality(self):
        if (self.inputs["World Origin"].default_value):
            bpy.ops.mesh.primitive_grid_add(
                x_subdivisions = int(self.inputs["X Subdivisions"].default_value),
                y_subdivisions = int(self.inputs["Y Subdivisions"].default_value),
                size = self.inputs["Size"].default_value,
                calc_uvs = self.inputs["Generate UVs"].default_value,
                align='WORLD',
                location=(0.0, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0)
            )
        else:
            bpy.ops.mesh.primitive_grid_add(
                x_subdivisions = int(self.inputs["X Subdivisions"].default_value),
                y_subdivisions = int(self.inputs["Y Subdivisions"].default_value),
                size = self.inputs["Size"].default_value,
                calc_uvs = self.inputs["Generate UVs"].default_value
            )