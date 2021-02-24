import bpy

from bpy.props import BoolProperty, IntProperty
from ...helper import print_log

class ScNode:
    node_executable: BoolProperty()
    first_time: BoolProperty()
    node_error: BoolProperty()
    scope_context_id: IntProperty()

    # This will hold all contexts for all ScNode instances, using hash(self) as an index.
    # This is a workaround to store ephemeral data, without using Property data.
    scope_contexts = {}

    @classmethod
    def poll(cls, _ntree):
        return _ntree.bl_idname == "ScNodeTree"
    
    def update_value(self, context):
        if (hasattr(context.space_data, "edit_tree") and context.space_data.edit_tree.bl_idname == "ScNodeTree"):
            context.space_data.edit_tree.execute_node()
        else:
            print_log("ScNode", None, "update_value", "Context is not Sorcar node tree")
        return None
    
    def reset(self, execute):
        # Reset node for next execution
        if (execute):
            self.first_time = True
            self.scope_context_id = -1
        self.set_color()
    
    def set_color(self):
        if (self.node_error and self == self.id_data.nodes.get(str(self.id_data.node))):
            self.color = (0.1, 0.1, 0.3)
        elif (self.node_error):
            self.color = (0.9, 0.1, 0.1)
        elif (self == self.id_data.nodes.get(str(self.id_data.node))):
            self.color = (0.1, 0.1, 0.9)
        else:
            self.color = (0.334, 0.334, 0.334)
    
    def init(self, context):
        # Initialise node with data
        self.use_custom_color = True
        self.set_color()

    def get_scope_context(self):
        return self.scope_contexts[hash(self)]

    def set_scope_context(self, context):
        self.scope_contexts[hash(self)] = context

    def get_scope_context_id(self):
        self_hash = hash(self)
        if self_hash in self.scope_contexts:
            context = self.scope_contexts[self_hash]
            return context['id']
        return -1

    def restore_scope_context_id(self, id):
        self_hash = hash(self)
        if self_hash in self.scope_contexts:
            context = self.scope_contexts[self_hash]
            context['id'] = id
        
    def increment_scope_context_id(self):
        self_hash = hash(self)
        if self_hash in self.scope_contexts:
            context = self.scope_contexts[self_hash]
            context['id'] += 1

    def draw_buttons(self, context, layout):
        if (self.node_executable):
            if (self == context.space_data.edit_tree.nodes.active):
                if (not self == context.space_data.edit_tree.nodes.get(str(context.space_data.edit_tree.node))):
                    layout.operator("sorcar.execute_node", text="Set Preview")
    
    def execute(self, scope_context, forced=False):
        # Execute node

        # Keep track of the last scope context we executed in. This will be used
        # to only execute once inside each loop iteration.
        self.set_scope_context(scope_context)
        id_changed = self.scope_context_id != scope_context['id']
        self.scope_context_id = scope_context['id']

        if (self.first_time or forced or id_changed):
            self.node_error = True
            if (self.init_in(forced)):
                if not (self.error_condition()):
                    self.pre_execute()
                    self.functionality()
                    self.node_error = not self.init_out(self.post_execute())
            self.first_time = False
        self.set_color()
        return not self.node_error
    
    def init_in(self, forced):
        for i in self.inputs:
            if (not i.execute(self.get_scope_context(), forced)):
                return False
        return True
    
    def error_condition(self):
        # Check for any error in input data
        return False
    
    def pre_execute(self):
        # Set/change focus or environment for execution
        pass
    
    def functionality(self):
        # Main operation using input values
        pass
    
    def post_execute(self):
        out = {}
        # Adjust parameters, reset focus/environment, set output
        return out
    
    def init_out(self, out):
        # Set all outputs
        if (not out):
            return False
        for i in out:
            if not (self.outputs[i].set(out[i])):
                return False
        return True