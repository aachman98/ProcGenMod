import bpy

from bpy.props import PointerProperty, StringProperty, BoolProperty
from .._base.node_base import ScNode
from ...helper import focus_on_object, remove_object, print_log, unique_name

class ScInputNode(ScNode):
    in_name: StringProperty(default="Object", update=ScNode.update_value)
    # in_uv: BoolProperty(default=True, update=ScNode.update_value)
    generated_objects: StringProperty(default="[]")

    def init(self, context):
        self.node_executable = True
        super().init(context)
        self.inputs.new("ScNodeSocketString", "Name").init("in_name")
        # self.inputs.new("ScNodeSocketBool", "Generate UVs").init("in_uv")
        self.outputs.new("ScNodeSocketObject", "Object")
    
    def copy(self, node):
        super().copy(node)
        self.generated_objects = "[]"
    
    def error_condition(self):
        return (
            self.inputs["Name"].default_value == ""
        )
    
    def pre_execute(self):
        # Clear generated objects
        # Check "first_time" to prevent unexpected deletion inside for-loop
        if (self.first_time):
            for obj in eval(self.generated_objects):
                # When obj is already deleted, remove_object() raises some exception.
                try:
                    remove_object(eval(obj))
                except:
                    print_log(self.name, None, "pre_execute",
                              "Invalid object: " + repr(obj))
            self.generated_objects = "[]"
    
    def post_execute(self):
        # WORKAROUND
        # Normally, Blender automatically makes the name of the object unique.
        # But we lose the old object because the name is overwritten by the
        # new object. We need to keep the old object's name and manually give
        # the new object a new unique name.
        name = unique_name(self.inputs["Name"].default_value)
        out_mesh = bpy.context.active_object
        out_mesh.name = name
        if (out_mesh.data):
            out_mesh.data.name = out_mesh.name
            
        tmp = eval(self.generated_objects)
        tmp.append(repr(out_mesh))
        self.generated_objects = repr(tmp)

        out = {}
        out["Object"] = out_mesh
        return out
