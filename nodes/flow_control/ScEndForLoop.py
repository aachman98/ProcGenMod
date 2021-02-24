import bpy

from bpy.props import IntProperty
from bpy.types import Node
from .._base.node_base import ScNode

class ScEndForLoop(Node, ScNode):
    bl_idname = "ScEndForLoop"
    bl_label = "End For Loop"

    in_iterations: IntProperty(default=5, min=1, update=ScNode.update_value)

    def init(self, context):
        self.node_executable = True
        super().init(context)
        self.inputs.new("ScNodeSocketInfo", "Begin For Loop")
        self.inputs.new("ScNodeSocketUniversal", "In")
        self.inputs.new("ScNodeSocketNumber", "Iterations").init("in_iterations", True)
        self.outputs.new("ScNodeSocketUniversal", "Out")
    
    def init_in(self, forced):
        return (
            self.inputs["Begin For Loop"].is_linked
            and self.inputs["Begin For Loop"].links[0].from_node.execute(self.get_scope_context(), forced)
            and self.inputs["Iterations"].execute(self.get_scope_context(), forced)
        )
    
    def error_condition(self):
        return (
            int(self.inputs["Iterations"].default_value) < 1
        )
    
    def functionality(self):
        context_id = self.get_scope_context_id()        
        for i in range (0, int(self.inputs["Iterations"].default_value)):
            self.increment_scope_context_id()
            self.inputs["Begin For Loop"].links[0].from_node.out_counter += 1
            self.inputs["In"].execute(self.get_scope_context(), False)
        self.restore_scope_context_id(context_id)
        self.inputs["Begin For Loop"].links[0].from_node.prop_locked = False
    
    def post_execute(self):
        out = {}
        out["Out"] = self.inputs["In"].default_value
        return out