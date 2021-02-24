import bpy

from bpy.props import IntProperty
from bpy.types import Node
from .._base.node_base import ScNode

SWITCH_MAX_INPUTS = 16

class ScSwitch(Node, ScNode):
    bl_idname = "ScSwitch"
    bl_label = "Switch"

    in_count: IntProperty(name="Count", update=ScNode.update_value)
    in_selector: IntProperty(name="Selector", update=ScNode.update_value)

    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketNumber", "Count").init("in_count", SWITCH_MAX_INPUTS)
        self.inputs.new("ScNodeSocketNumber", "Selector").init("in_selector", -1)
        for i in range(SWITCH_MAX_INPUTS):
            self.inputs.new("ScNodeSocketUniversal", "Input%d" % (i,))
        self.inputs.new("ScNodeSocketUniversal", "Default")
        self.outputs.new("ScNodeSocketUniversal", "Value")
    
    def init_in(self, forced):
        if self.inputs["Count"].execute(self.get_scope_context(), forced):
            count = self.inputs["Count"].default_value       
            count = min(count, SWITCH_MAX_INPUTS)
            if self.inputs["Selector"].execute(self.get_scope_context(), forced):
                selector = self.inputs["Selector"].default_value
                if selector >= 0 and selector < count:
                    return self.inputs["Input%d" % (selector,)].execute(self.get_scope_context(), forced)
                return self.inputs["Default"].execute(self.get_scope_context(), forced)
        return False

    def post_execute(self):
        count = self.inputs["Count"].default_value
        count = min(count, SWITCH_MAX_INPUTS)
        selector = self.inputs["Selector"].default_value
        if selector >= 0 and selector < count:
            return {"Value": self.inputs["Input%d" % (selector,)].default_value}
        return {"Value": self.inputs["Default"].default_value}
