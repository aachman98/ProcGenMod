import bpy
import numpy

from bpy.props import FloatProperty, IntProperty, StringProperty
from bpy.types import Node
from .._base.node_base import ScNode

WEIGHTED_INDEX_MAX_INPUTS = 16

class ScWeightedIndex(Node, ScNode):
    bl_idname = "ScWeightedIndex"
    bl_label = "Weighted Index"

    prop_random_state: StringProperty()
    in_seed: IntProperty(name="Seed", min=0, update=ScNode.update_value)
    in_weight0: FloatProperty(name="Weight0", min=0, update=ScNode.update_value)
    in_weight1: FloatProperty(name="Weight1", min=0, update=ScNode.update_value)
    in_weight2: FloatProperty(name="Weight2", min=0, update=ScNode.update_value)
    in_weight3: FloatProperty(name="Weight3", min=0, update=ScNode.update_value)
    in_weight4: FloatProperty(name="Weight4", min=0, update=ScNode.update_value)
    in_weight5: FloatProperty(name="Weight5", min=0, update=ScNode.update_value)
    in_weight6: FloatProperty(name="Weight6", min=0, update=ScNode.update_value)
    in_weight7: FloatProperty(name="Weight7", min=0, update=ScNode.update_value)
    in_weight8: FloatProperty(name="Weight8", min=0, update=ScNode.update_value)
    in_weight9: FloatProperty(name="Weight9", min=0, update=ScNode.update_value)
    in_weight10: FloatProperty(name="Weight10", min=0, update=ScNode.update_value)
    in_weight11: FloatProperty(name="Weight11", min=0, update=ScNode.update_value)
    in_weight12: FloatProperty(name="Weight12", min=0, update=ScNode.update_value)
    in_weight13: FloatProperty(name="Weight13", min=0, update=ScNode.update_value)
    in_weight14: FloatProperty(name="Weight14", min=0, update=ScNode.update_value)
    in_weight15: FloatProperty(name="Weight15", min=0, update=ScNode.update_value)

    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketNumber", "Seed").init("in_seed", True)
        for i in range(WEIGHTED_INDEX_MAX_INPUTS):
            self.inputs.new("ScNodeSocketNumber", "Weight%d" % (i,)).init("in_weight%d" % (i,), True)
        self.outputs.new("ScNodeSocketNumber", "Value")
    
    def init_in(self, forced):
        success = True
        success = success and self.inputs["Seed"].execute(self.get_scope_context(), forced)
        for i in range(WEIGHTED_INDEX_MAX_INPUTS):
            success = success and self.inputs["Weight%d" % (i,)].execute(self.get_scope_context(), forced)
        return success

    def post_execute(self):
        seed = self.inputs["Seed"].default_value
        rs = numpy.random.RandomState(int(seed))
        if (not self.first_time):
            rs.set_state(eval(self.prop_random_state))
        w = rs.rand()
        self.prop_random_state = repr(rs.get_state())

        total = 0
        for i in range(WEIGHTED_INDEX_MAX_INPUTS):
            total += self.inputs["Weight%d" % (i,)].default_value

        running = 0
        for i in range(WEIGHTED_INDEX_MAX_INPUTS):
            running += self.inputs["Weight%d" % (i,)].default_value
            if w <= running / total:
                return {"Value": i}

        return {"Value": 0}
