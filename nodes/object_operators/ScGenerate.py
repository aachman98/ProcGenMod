import sys
import bpy
import numpy
import inspect
from numpy import array, uint32
import re

from mathutils import Vector, Matrix, Euler
from bpy.props import PointerProperty, StringProperty, EnumProperty, BoolProperty, IntProperty
from bpy.types import Node
from .._base.node_base import ScNode
from .._base.node_operator import ScObjectOperatorNode
from ...helper import focus_on_object, remove_object, print_log

DEBUG_PRINT = True

PROP_WEIGHT_KEY = "weight"
PROP_LINK_KEY = "link"
PROP_INSTANCER_KEY = "instancer"

# TODO:
# * Allow gen_instancer to accept collections/definitions, or evaluable code if it contains a ( or ).
# * Create a simple 2D layout system using bounding boxes and filling them with scaled instances, which flows in X, and then Y.
# * Tag object to recursively combine and bake all child meshes and modifiers
# 

# Debug util

def debug_log(title, str):
    if DEBUG_PRINT:
        print_log(title, str)

# DSL for writing grammars

class DslContext:
    def __init__(self, rand_state, property_prefix, start_link):
        # the only random selection state allowed
        self.rand_state = rand_state

        # any custom property will be assumed to have this prefix
        self.property_prefix = property_prefix

        # The following three values are mutually exclusive. We've either just created an object,
        # or created a virtual object from a definition with aliased links, or we've followed a link.

        # the current object in the production
        self.cur_obj = None
        # definitions must set aliases. if cur_obj_aliases != None, the cur_obj's children will
        # be ignored for following links, and we'll only use the aliases.
        # instance nodes will be followed.
        self.cur_obj_aliases = None
        # the last link moved to
        self.cur_link = start_link

        # the current transform in the current link's frame of reference
        # every link that's followed resets this
        self.cur_link_matrix = start_link.matrix_world.copy()
        self.cur_location = Vector((0,0,0))
        self.cur_rotation = Euler((0,0,0), 'XYZ')
        self.cur_scale = Vector((1,1,1))

        # definitions at our disposal to search for
        self.definitions = {}
        # while defining, we can capture all exports for use in that definition during execution
        # that set of captures will be used for linking after the definition has executed
        self.export_captures = []

        # scopes let us do a production, and pop back to a current state
        self.scopes = []

        # list of all objects generated while running
        self.generated_objects = []

        # errors contain a list of errors found during the preparation or execution phases
        self.errors = []

    def print_state(self, title):
        if DEBUG_PRINT:
            debug_log("print_state", "%s: obj:%s obj_aliases:%s link:%s" % (title, repr(self.cur_obj), repr(self.cur_obj_aliases), repr(self.cur_link)))

    def is_production_list(self, text):
        return re.match(r"^\s*\[.*\]\s*$", text, flags=re.MULTILINE|re.DOTALL) != None

    def evaluate_production(self, text):
        try:
            if not self.is_production_list(text):
                self.add_error("Rule production is not a list: %s" % (text,))
                self.check_for_errors("Parse")
                return False

            op_list = eval(text)

            for op in op_list:
                op.prepare(self)
                if self.check_for_errors("Preparation"):
                    return False
                op.execute(self)
                if self.check_for_errors("Execution"):
                    return False
        except:
            self.add_error("Exception while evaluating rule production: %s" % str(sys.exc_info()[0]))
            self.check_for_errors("Parse")
            return False

        return True

    def add_generated_object(self, obj):
        self.generated_objects.append(obj)

    def _reset_transform(self):
        self.cur_location = Vector((0,0,0))
        self.cur_rotation = Euler((0,0,0), 'XYZ')
        self.cur_scale = Vector((1,1,1))

    def compute_world_matrix(self):
        mat_loc = Matrix.Translation(self.cur_location).to_4x4()
        mat_rot = Euler(self.cur_rotation, 'XYZ').to_matrix().to_4x4()
        mat_sca = Matrix.Diagonal(self.cur_scale).to_4x4()
        mat = mat_loc @ mat_rot @ mat_sca
        return self.cur_link_matrix @ mat

    # parent object to a parent, and select object after
    def parent_object(self, obj, parent):
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        parent.select_set(True)
        bpy.context.view_layer.objects.active = parent

        bpy.ops.object.parent_set(type="OBJECT", keep_transform=False)

        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

    def set_current_object(self, obj):
        self.cur_obj = obj
        self.cur_obj_aliases = None
        self.cur_link = None
        self.print_state("set_current_object")

    def set_current_link(self, link):
        self.cur_link = link
        self.cur_link_matrix = link.matrix_world.copy()
        self.cur_obj = None
        self.cur_obj_aliases = None
        self._reset_transform()
        self.print_state("set_current_link")

    def get_current_link(self):
        return self.cur_link

    def get_custom_property_value(self, obj, partial_key):
        key = self.property_prefix + "_" + partial_key
        if obj != None and (key in obj.keys()):
            return obj[key]
        return None

    def get_link_parent(self, link):
        parent = link.parent
        while parent:
            next_parent = parent.parent
            if not next_parent or self.get_custom_property_value(next_parent, PROP_LINK_KEY) or self.get_custom_property_value(next_parent, PROP_INSTANCER_KEY):
                return parent
            parent = next_parent
        return None

    def _get_links_recursive(self, link_list, node, re_comp):
        for child in node.children:
            child_link_name = self.get_custom_property_value(child, PROP_LINK_KEY)
            if child_link_name != None:
                if re_comp.match(child_link_name):
                    link_list.append( (child_link_name, child) )
            else:
                self._get_links_recursive(link_list, child, re_comp)

    def get_matching_links(self, pattern, node=None):
        link_list = []

        print_log("Debug0", "Pattern:%s Aliases:%s Obj:%s" % (pattern, repr(self.cur_obj_aliases), repr(self.cur_obj)))

        re_comp = re.compile(pattern)
        if node != None:
            self._get_links_recursive(link_list, node, re_comp)
        elif self.cur_obj_aliases:
            for name in self.cur_obj_aliases:
                if re_comp.match(name) != None:
                    link_list.append( (name, self.cur_obj_aliases[name]) )
        elif self.cur_obj:
            self._get_links_recursive(link_list, self.cur_obj, re_comp)

        print_log("Debug1", "List:%s" % (repr(link_list),))

        return link_list

    def _get_leaf_instancers_recursive(self, node, leaves):
        instancer_string = self.get_custom_property_value(node, PROP_INSTANCER_KEY)
        if instancer_string != None and len(node.children) == 0:
            # leaf
            leaves.append( (instancer_string, node) )
        else:
            for child in node.children:
                self._get_leaf_instancers_recursive(child, leaves)

    def get_leaf_instancers(self):
        if self.cur_obj != None:
            leaves = []
            self._get_leaf_instancers_recursive(self.cur_obj, leaves)
            return leaves
        return None

    def get_child_links(self):
        return self.get_matching_links(".*")

    def move_to_link(self, name):
        links = self.get_matching_links(name)
        for pair in links:
            link_name = pair[0]
            link = pair[1]
            if name == link_name:
                self.set_current_link(link)
                self.print_state("move_to_link")
                return
        self.print_state("move_to_link(not found)")

    def create_link(self, name):
        if self.cur_obj == None:
            self.add_error("Warning: Ignored creating a link without an active object.")
        else:
            mat = self.compute_world_matrix()
            loc, rot, sca = mat.decompose()
            bpy.ops.object.empty_add(type='ARROWS', align='WORLD', location=loc, rotation=rot, scale=sca)
            obj = bpy.context.view_layer.objects.active
            self.parent_object(obj, self.cur_obj)

    def set_definition(self, name, sequence):
        self.definitions[name] = sequence

    def get_definition(self, name):
        if name in self.definitions:
            return self.definitions[name]
        return None

    def push_scope(self):
        self.scopes.append({
            'cur_obj': self.cur_obj,
            'cur_obj_aliases': self.cur_obj_aliases,
            'cur_link': self.cur_link,
            'cur_link_matrix': self.cur_link_matrix.copy(),
            'cur_location' : self.cur_location.copy(),
            'cur_rotation' : self.cur_rotation.copy(),
            'cur_scale' : self.cur_scale.copy()
        })
        self.print_state("push_scope")

    def get_scope(self):
        count = len(self.scopes)
        if count > 0:
            return self.scopes[count - 1]
        return None

    def pop_scope(self):
        top = self.scopes.pop()
        self.cur_obj = top['cur_obj']
        self.cur_obj_aliases = top['cur_obj_aliases']
        self.cur_link = top['cur_link']
        self.cur_link_matrix = top['cur_link_matrix'].copy()
        self.cur_location = top['cur_location'].copy()
        self.cur_rotation = top['cur_rotation'].copy()
        self.cur_scale = top['cur_scale'].copy()
        self.print_state("pop_scope")
        
    def push_define_export_capture(self):
        self.print_state("push_define_export_capture")
        self.export_captures.append({
            'object': None,
            'aliases': {}
        })

    def _get_define_export_capture(self):
        count = len(self.export_captures)
        if count > 0:
            return self.export_captures[count - 1]
        return None

    def define_link_export(self, alias):
        cap = self._get_define_export_capture()
        if cap:
            cap['aliases'][alias] = self.cur_link

    def pop_define_export_capture(self):
        top = self.export_captures.pop()
        obj = top['object']
        # If no object was instanced during capture, don't consider
        # this a valid capture.
        if obj != None:
            self.cur_obj = obj
            self.cur_obj_aliases = top['aliases']
            self.cur_link = None
        self.print_state("pop_define_export_capture")

    def move_hierarchy_collections(self, item, from_collection, to_collection):
        if from_collection != None:
            from_collection.objects.unlink(item)
        if to_collection != None:
            to_collection.objects.link(item)

        for child in item.children:
            self.move_hierarchy_collections(child, from_collection, to_collection)

    def move_hierarchy_to_link(self, obj, link=None):
        # move hierarchy to parent's collection
        # first remove the object's link to current collection
        obj_collection = None
        if len(obj.users_collection) > 0:
            obj_collection = obj.users_collection[0]        

        parent = self.get_current_link()
        if link != None:
            parent = link

        parent_collection = None
        if len(parent.users_collection) > 0:
            parent_collection = parent.users_collection[0]

        self.move_hierarchy_collections(obj, obj_collection, parent_collection)
        
        # final parenting within collection
        self.parent_object(obj, parent)

    def notify_instance_created(self, obj):
        cap = self._get_define_export_capture()
        # track first object for an export capture--this 
        # will be the cur_obj after capture.
        if cap and (cap['object'] == None):
            cap['object'] = obj

    def create_instance(self, name):
        # check if it's a bounding link
        bbox = None
        if self.cur_link and self.cur_link.type == 'EMPTY' and self.cur_link.empty_display_type == 'CUBE':
            bbox = self.cur_link.empty.scale

        sequence = self.get_definition(name)
        if sequence != None:
            self.push_define_export_capture()
            for item in sequence:
                if isinstance(item, DslOp):
                    item.execute(self)
            self.pop_define_export_capture()
        elif name in bpy.data.collections:
            selected_obj = None
            src_collection = bpy.data.collections[name]
            src_objects = []
            if src_collection != None:                            
                for ch in src_collection.objects:
                    # check for top level
                    if ch.parent == None:
                        src_objects.append(ch)
            weight_total = 0
            weight_pairs = []
            if len(src_objects) > 0:                
                for candidate in src_objects:
                    weight = self.get_custom_property_value(candidate, PROP_WEIGHT_KEY)
                    if type(weight) not in [int, float]:
                        weight = 1.0
                    weight_total += weight
                    weight_pairs.append((candidate, weight))
                rand01 = self.rand_state.rand()
                weight_thresh = rand01 * weight_total
                weight_sum = 0

                for pair in weight_pairs:
                    weight_sum += pair[1]
                    if weight_sum > weight_thresh:
                        selected_obj = pair[0]
                        break
                
                if selected_obj == None:                
                    selected_obj = src_objects[len(src_objects) - 1]

            if selected_obj != None:
                # hierarchically duplicate object
                bpy.ops.object.select_all(action="DESELECT")
                selected_obj.select_set(True)
                bpy.context.view_layer.objects.active = selected_obj
                bpy.ops.object.select_grouped(extend=True, type='CHILDREN_RECURSIVE')
                bpy.ops.object.duplicate()

                copy = bpy.context.view_layer.objects.active
                if copy != None:
                    copy.matrix_world = self.compute_world_matrix()

                    # move to parent's collection
                    self.move_hierarchy_to_link(copy)

                    self.set_current_object(copy)
                    self.add_generated_object(copy)
                    self.notify_instance_created(copy)
        
        instancers = self.get_leaf_instancers()
        if instancers != None:
            for inst in instancers:
                # treat gen_instance as links that get automatically instanced
                inst_string = inst[0]
                inst_obj = inst[1]

                if self.is_production_list(inst_string):
                    # eval list
                    self.push_scope()
                    self.set_current_link(inst_obj)
                    if not self.evaluate_production(inst_string):
                        self.add_error("Could not evaluate instancer on object %s" % (inst_obj.name,))
                    self.pop_scope()
                else:
                    # name
                    self.push_scope()
                    self.set_current_link(inst_obj)
                    self.create_instance(inst_string)
                    self.pop_scope()

    def add_error(self, error):
        self.errors.append(error)

    def check_for_errors(self, title):
        for error in self.errors:
            print_log("Generate:", "%s: Error: %s" % (title, error,))

        return len(self.errors) > 0

    def clear_errors(self):
        self.errors = []

class DslBase:
    def register(self):
        trace = inspect.stack()
        if trace != None:
            self.script_line = trace[2][2]
        else:
            self.script_line = -1

    def get_script_line(self):
        return self.script_line

class DslValue(DslBase):
    def __init__(self):
        pass

    def prepare(self, ctx):
        return True

    def execute(self):
        pass

class GnRange(DslValue):
    def __init__(self, min_value, max_value):
        self.register()
        self.min_value = min_value
        self.max_value = max_value

    def prepare(self, ctx):
        if not isinstance(self.min_value, int):
            ctx.add_error("GnRange: min_value not an integer")
            return False
        elif not isinstance(self.max_value, int):
            ctx.add_error("GnRange: max_value not an integer")
            return False
        elif self.min_value > self.max_value:
            ctx.add_error("GnRange: max_value is less than min_value")
            return False
        return True

    def evaluate(self, ctx):
        return ctx.rand_state.randint(self.min_value, self.max_value + 1)

# weights: a list of tuples where the first is the weight, the second is the value
# on evaluation, will use ctx random state to pick a value
class GnWeighted(DslValue):
    def __init__(self, weights):
        self.register()
        self.weights = weights

    def prepare(self, ctx):
        shape_error = False
        if not isinstance(self.weights, list) and not isinstance(self.weights, tuple):
            shape_error = True
        else:
            for weight in self.weights:
                if not isinstance(weight, list) and not isinstance(weight, tuple):
                    shape_error = True
                    break
        if shape_error:
            ctx.add_error("GnWeighted: weights must be tuple or list of tuple or list pairs")
            return False
        return True

    def evaluate(self, ctx):
        total = 0
        for w in self.weights:
            total += w[0]
        sum = 0
        thresh = total * ctx.rand_state.rand()
        value = None
        for w in self.weights:
            sum += w[0]
            if sum >= thresh:
                value = w[1]
                break
        
        if value == None and len(self.weights) > 0:
            value = self.weights[self.weights - 1]

        return value

# For a value to be evaluated as compilation (prepare) time
# Caches the result for use during the evaluate() call
class GnStatic(DslValue):
    def __init__(self, value):
        self.register()
        self.value = value

    def prepare(self, ctx):
        if isinstance(self.value, DslValue):
            self.value = self.value.evaluate(ctx)
            while isinstance(self.value, DslValue):
                self.value = self.value.evaluate(ctx)
        return True

    def evaluate(self, ctx):
        return self.value

# An operation in the DSL
# Contains helper methods
class DslOp(DslBase):
    def __init__(self):
        pass

    def prepare(self, ctx):
        return True

    def assert_link_op(self, ctx):
        if ctx.cur_link != None:
            return True
        name = type(self).__name__
        line = self.get_script_line()
        ctx.add_error("%s (line %d): Error: Expected to be in an operation under a direct link." % (name, line))
        return False

    def assert_instance_op(self, ctx):
        if ctx.cur_obj != None:
            return True
        name = type(self).__name__
        line = self.get_script_line()
        ctx.add_error("%s (line %d): Error: Expected to be in an operation under a direct geometry instance." % (name, line))
        return False

    def prepare_value(self, ctx, value):
        if isinstance(value, DslValue):
            if not value.prepare(ctx):
                return False
        return True

    def evaluate_value(self, ctx, value):
        while isinstance(value, DslValue):
            value = value.evaluate(ctx)
        return value

# Define a named macro that can be executed as needed
# Definitions require explicit GnExportLink after the GnLink is made
class GnDefine(DslOp):
    def __init__(self, name, sequence):
        self.register()
        self.name = name
        self.sequence = sequence

    def prepare(self, ctx):
        if not isinstance(self.name, str):
            ctx.add_error("GnDefine: name of definition must be string literal")
            return False

        if not isinstance(self.sequence, list) and not isinstance(self.sequence, tuple):
            ctx.add_error("GnDefine: sequence must be list or tuple")
            return False

        for item in self.sequence:
            if not item.prepare(ctx):
                return False

        ctx.set_definition(self.name, self.sequence)
        return True

    def execute(self, ctx):
        pass

# A definition of the exported links in a command definition above
class GnExportLink(DslOp):
    def __init__(self, alias):
        self.register()
        self.alias = alias

    def prepare(self, ctx):
        return self.prepare_value(ctx, self.alias)

    def execute(self, ctx):
        if not self.assert_link_op(ctx):
            return

        alias = self.evaluate_value(ctx, self.alias)
        ctx.define_link_export(alias)

# A scope frame that contains a sequence. When finished, the context's object and link states return
# to where they were before the scope.
class GnScope(DslOp):
    def __init__(self, sequence):
        self.register()
        self.sequence = sequence

    def prepare(self, ctx):
        if not isinstance(self.sequence, list) and not isinstance(self.sequence, tuple):
            ctx.add_error("GnScope: scope sequence must be of type list or tuple")
            return False

        for item in self.sequence:
            if not item.prepare(ctx):
                return False

        return True

    def execute(self, ctx):
        ctx.push_scope()
        for item in self.sequence:
            item.execute(ctx)
        ctx.pop_scope()

# Repeat the contained sequence some number of times.
# Count can be any DslValue instance or integer constant
class GnRepeat(DslOp):
    def __init__(self, count, sequence):
        self.register()
        self.count = count
        self.sequence = sequence        

    def prepare(self, ctx):
        if not self.prepare_value(ctx, self.count):
            return False
        for item in self.sequence:
            if not item.prepare(ctx):
                return False
        return True

    def execute(self, ctx):
        count = self.evaluate_value(ctx, self.count)
        for _ in range(count):
            for item in self.sequence:
                item.execute(ctx)

# Create an instance of an object from a name, first looking in definitions, and then
# by looking for an identically named collection, and copying a weighted template object it
class GnInstance(DslOp):
    def __init__(self, name):
        self.register()
        self.name = name

    def prepare(self, ctx):
        return self.prepare_value(ctx, self.name)

    def execute(self, ctx):
        if not self.assert_link_op(ctx):
            return

        name = self.evaluate_value(ctx, self.name)
        ctx.create_instance(name)

class GnCopyParentLinkChildren(DslOp):
    def __init__(self, link, mirror=None):
        self.register()
        self.link = link
        self.mirror = mirror

    def prepare(self, ctx):
        return self.prepare_value(ctx, self.link)

    def execute(self, ctx):
        if not self.assert_link_op(ctx):
            return

        src_link_name = self.evaluate_value(ctx, self.link)
        dest_link = ctx.get_current_link()
        if dest_link != None:
            parent = ctx.get_link_parent(dest_link)

            print_log("Debug2", "Parent: %s" % (repr(parent),))

            if parent != None:
                links = ctx.get_matching_links(src_link_name, node=parent)
                if len(links) > 0:
                    child = links[0][1] # get the first pair, link is index 1
                    if child:
                        for gch in child.children:
                            # hierarchically duplicate all children
                            bpy.ops.object.select_all(action="DESELECT")
                            gch.select_set(True)
                            bpy.context.view_layer.objects.active = gch
                            bpy.ops.object.select_grouped(extend=True, type='CHILDREN_RECURSIVE')
                            bpy.ops.object.duplicate()

                            gch_copy = bpy.context.view_layer.objects.active
                            if gch_copy != None:
                                gch_copy.matrix_world = ctx.compute_world_matrix()

                                # move to parent's collection
                                ctx.move_hierarchy_to_link(gch_copy, dest_link)

                                scale_tuple = None
                                if self.mirror == 'x':
                                    scale_tuple = (1, 0, 0)
                                elif self.mirror == 'y':
                                    scale_tuple = (0, 1, 0)
                                elif self.mirror == 'z':
                                    scale_tuple = (0, 0, 1)

                                if scale_tuple != None:
                                    bpy.ops.object.select_all(action="DESELECT")
                                    gch_copy.select_set(True)
                                    bpy.context.view_layer.objects.active = gch_copy

                                    mat_mirror = Matrix.Scale(-1, 4, scale_tuple)
                                    gch_copy.matrix_local = mat_mirror @ gch_copy.matrix_local
                                   
                                    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

                                    bpy.ops.object.editmode_toggle()
                                    bpy.ops.mesh.select_all(action='SELECT')
                                    bpy.ops.mesh.flip_normals()
                                    bpy.ops.object.mode_set()

                                ctx.add_generated_object(gch_copy)

# Create a link dynamically at the current position, but do not follow it.
# In any entered link, the position is by default 0,0,0. A position can be set by GnMove.
class GnCreateLink(DslOp):
    def __init__(self, name):
        self.register()
        self.name = name

    def prepare(self, ctx):
        return self.prepare_value(ctx, self.name)

    def execute(self, ctx):
        if not self.assert_instance_op(ctx):
            return

        name = self.evaluate_value(ctx, self.name)
        ctx.create_link(name)

# In the state machine, move from the last made object to a named link
# If the last named object was a dictionary defined macro, it will search the current exports.
# otherwise, it will look for children with a <prefix>_link custom property where the value 
# matches the link name.
class GnLink(DslOp):
    def __init__(self, name):
        self.register()
        self.name = name

    def prepare(self, ctx):
        return self.prepare_value(ctx, self.name)

    def execute(self, ctx):
        name = self.evaluate_value(ctx, self.name)
        ctx.move_to_link(name)

# Search for a link based on a pattern, and run the sequence on each one.
class GnEachLink(DslOp):
    def __init__(self, pattern, sequence):
        self.register()
        self.pattern = pattern
        self.sequence = sequence

    def prepare(self, ctx):
        if not isinstance(self.pattern, str):
            ctx.add_error("GnEachLink: search pattern must be string literal")
            return False
        if not isinstance(self.sequence, list) and not isinstance(self.sequence, tuple):
            ctx.add_error("GnEachLink: scope sequence must be of type list or tuple")
            return False
        for item in self.sequence:
            if not item.prepare(ctx):
                return False
        return True

    def execute(self, ctx):                
        if not self.assert_instance_op(ctx):
            return

        links = ctx.get_matching_links(self.pattern)        
        for pair in links:
            link = pair[1]
            ctx.push_scope()
            ctx.set_current_link(link)
            for item in self.sequence:
                item.execute(ctx)
            ctx.pop_scope()

# In the state machine, move from the last made object to a named link
# If the last named object was a dictionary defined macro, it will search the current exports.
# otherwise, it will look for children with a <prefix>_link custom property where the value 
# matches the link name.
class GnMaybe(DslOp):
    def __init__(self, ratio, sequence):
        self.register()
        self.ratio = ratio
        self.sequence = sequence

    def prepare(self, ctx):
        if not self.prepare_value(ctx, self.ratio):
            ctx.add_error("GnMaybe: ratio is invalid.")
            return False
        if not isinstance(self.sequence, list) and not isinstance(self.sequence, tuple):
            ctx.add_error("GnMaybe: scope sequence must be of type list or tuple")
            return False
        for item in self.sequence:
            if not item.prepare(ctx):
                return False
        return True

    def execute(self, ctx):
        if ctx.rand_state.rand() <= self.ratio:
            for item in self.sequence:
                item.execute(ctx)

class GnMove(DslOp):
    def __init__(self, location, absolute=False):
        self.register()
        self.location = location
        self.absolute = absolute

    def prepare(self, ctx):
        if type(self.absolute) != type(True):
            ctx.add_error("GnMove: absolute key must be True or False.")
            return False
        if not isinstance(self.location, list) and not isinstance(self.location, tuple):
            ctx.add_error("GnMove: location must be of type list or tuple")
            return False
        return True

    def execute(self, ctx):
        if self.absolute:
            ctx.cur_location = Vector(self.location)
        else:
            ctx.cur_location += Vector(self.location)

class GnRotate(DslOp):
    def __init__(self, rotation, absolute=False):
        self.register()
        self.rotation = rotation
        self.absolute = absolute

    def prepare(self, ctx):
        if type(self.absolute) != type(True):
            ctx.add_error("GnRotate: absolute key must be True or False.")
            return False
        if not isinstance(self.rotation, list) and not isinstance(self.rotation, tuple):
            ctx.add_error("GnRotate: rotation must be an Euler XYZ representation of type list or tuple")
            return False
        return True

    def execute(self, ctx):
        if self.absolute:
            ctx.cur_rotation = Euler(self.rotation, 'XYZ')
        else:
            ctx.cur_rotation.rotate(Euler(self.rotation, 'XYZ'))

class GnScale(DslOp):
    def __init__(self, scale, absolute=False):
        self.register()
        self.scale = scale
        self.absolute = absolute

    def prepare(self, ctx):
        if type(self.absolute) != type(True):
            ctx.add_error("GnScale: absolute key must be True or False.")
            return False
        if not isinstance(self.scale, list) and not isinstance(self.scale, tuple):
            ctx.add_error("GnScale: scale must be of type list or tuple")
            return False
        return True

    def execute(self, ctx):
        if self.absolute:
            ctx.cur_scale = Vector(self.scale)
        else:
            print_log("Scale Pre", "ctx.cur_scale:%s self.scale:%s" % (repr(ctx.cur_scale), repr(self.scale)))

            ctx.cur_scale = Vector((
                ctx.cur_scale[0] * self.scale[0],
                ctx.cur_scale[1] * self.scale[1],
                ctx.cur_scale[2] * self.scale[2]
            ))

# Generator node

class ScGenerate(Node, ScObjectOperatorNode):
    bl_idname = "ScGenerate"
    bl_label = "Generate"

    prop_random_state: StringProperty()
    in_file: StringProperty(subtype='FILE_PATH', update=ScNode.update_value)
    in_prefix: StringProperty(default="gen", update=ScNode.update_value)
    in_seed: IntProperty(default=0, min=0, update=ScNode.update_value)
    in_max_depth: IntProperty(default=10, min=0, update=ScNode.update_value)
    in_clear_children: BoolProperty(default=True, update=ScNode.update_value)
    prop_obj_array: StringProperty(default="[]")

    def init(self, context):
        super().init(context)
        self.inputs.new("ScNodeSocketString", "File").init("in_file", True)
        self.inputs.new("ScNodeSocketString", "Prefix").init("in_prefix", False)
        self.inputs.new("ScNodeSocketNumber", "Seed").init("in_seed", True)
        self.inputs.new("ScNodeSocketNumber", "Max Depth").init("in_max_depth", True)
        self.inputs.new("ScNodeSocketBool", "Clear Children").init("in_clear_children", False)
        self.outputs.new("ScNodeSocketArray", "Generated Objects")
        
    def error_condition(self):
        return (
            super().error_condition()
            or self.inputs["File"].default_value == ""
        )
    
    def pre_execute(self):
        super().pre_execute()
        self.prop_obj_array = "[]"

    def functionality(self):
        pass
        # 
    
    def post_execute(self):
        seed = abs(self.inputs["Seed"].default_value)

        rs = numpy.random.RandomState(int(seed))
        if (not self.first_time):
            debug_log("post_execute:", "RS:" + str(self.prop_random_state))
            rs.set_state(eval(self.prop_random_state))

        generated_objects = []

        file_text = ''
        try:
            file_path = self.inputs["File"].default_value
            file_path = bpy.path.abspath(self.inputs["File"].default_value)
            fd = open(file_path, "r")
            file_text = fd.read()
            fd.close()
        except:
            ex = sys.exc_info()[0]
            print_log("ScGenerate", "There was an error loading the file: %s" % (ex,))

        debug_log("ScGenerate", "Read %d characters from file %s" % (len(file_text), file_path))

        if isinstance(file_text, str) and file_text != "":
            start_obj = self.inputs["Object"].default_value
            if start_obj != None:
                # clear start object's children
                if self.inputs["Clear Children"].default_value:
                    for child in start_obj.children:
                        remove_object(child, hierarchy=True)

                # root of rule recursion
                dsl_ctx = DslContext(rs, self.inputs["Prefix"].default_value, start_obj)
                if dsl_ctx.evaluate_production(file_text):
                    generated_objects = dsl_ctx.generated_objects

        self.prop_obj_array = repr(generated_objects)
        self.prop_random_state = repr(rs.get_state())

        out = super().post_execute()
        out["Generated Objects"] = self.prop_obj_array
        return out
    
    def free(self):
        for object in self.prop_obj_array[1:-1].split(', '):
            try:
                obj = eval(object)
            except:
                print_log(self.id_data.name, self.name, "free", "Invalid object: " + object)
                continue
            self.id_data.unregister_object(obj)