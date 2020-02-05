import bpy

from bpy.props import FloatProperty, StringProperty
from bpy.types import Node
from .._base.node_base import ScNode
from .._base.node_operator import ScObjectOperatorNode
from ...helper import remove_object, print_log

class ScDuplicateObject(Node, ScObjectOperatorNode):
    bl_idname = "ScDuplicateObject"
    bl_label = "Duplicate Object"

    generated_objects: StringProperty(default="[]")
    
    def init(self, context):
        super().init(context)
        self.outputs.new("ScNodeSocketObject", "Duplicate Object")
    
    def copy(self, node):
        super().copy(node)
        self.generated_objects = "[]"
    
    def pre_execute(self):
        # Check first_time to prevent unexpected deletion inside for-loop
        if (self.first_time):
            for obj in eval(self.generated_objects):
                # When obj is already deleted, remove_object() raises some exception.
                try:
                    remove_object(eval(obj))
                except:
                    print_log(self.name, None, "pre_execute",
                              "Invalid object: " + repr(obj))
            self.generated_objects = "[]"
        super().pre_execute()
    
    def functionality(self):
        bpy.ops.object.duplicate()
    
    def post_execute(self):
        # Store duplicated object to delete it before re-execute this node.
        tmp = eval(self.generated_objects)
        tmp.append(repr(bpy.context.active_object))
        self.generated_objects = repr(tmp)

        out = super().post_execute()
        out["Duplicate Object"] = bpy.context.active_object
        return out
