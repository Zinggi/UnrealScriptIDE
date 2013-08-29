#-----------------------------------------------------------------------------------
# UnrealScriptIDE Data
#-----------------------------------------------------------------------------------
#
#   The data class stores all data needed by my plug-in.
#   This includes classes, all functions and variables of those classes, as well as struts.
#
# ! TODO:
#       - enum support
#
# (c) Florian Zinggeler
#-----------------------------------------------------------------------------------
import sublime
import re

# if the helper panel is displayed, this is true
# ! (TODO): use an event instead
b_helper_panel_on = False
output_view = None


# prints the text to the "helper panel" (Actually the console)
# ! (TODO): fire show_helper_panel
def print_to_panel(view, text, b_overwrite=True):
    global b_helper_panel_on, output_view
    # get_output_panel doesn't "get" the panel, it *creates* it, so we should only call get_output_panel once
    if b_overwrite or not output_view:
        panel = view.window().get_output_panel('UnrealScriptAutocomplete_panel')
        output_view = panel
    else:
        panel = output_view
    panel_edit = panel.begin_edit()
    panel.insert(panel_edit, panel.size(), text)
    panel.end_edit(panel_edit)
    if not b_overwrite:
        panel.show(panel.size())
    view.window().run_command("show_panel", {"panel": "output.UnrealScriptAutocomplete_panel"})
    b_helper_panel_on = True


# base class for adding new auto-complete suggestions
# takes care of building up the data structure and handling it.
class UnrealData:
    # stores all classes
    # At the beginning, search trough the whole source folder and fill this
    # These classes also contain their functions and variables if they were already parsed.
    _classes = []

    # stores all functions and variables to use as completions on a file
    # ! TODO:   If it is fast enough, make use of the classes objects and abandon this, as it is redundant
    #           instead save all class objects to be used on one file
    # now: (filename, functions, variables)
    _completions_for_file = []
    # files that have already been parsed (and therefore are inside _completions_for_file)
    _filenames = []

    # -------------
    # these store the current completions. Completions will be extracted based on those arrays.
    # -----
    # stores all functions and information about them
    _functions = []
    # stores all variables
    _variables = []

    # the class we wanted to load completions from
    completion_class = None

    # inbuilt functions should always be present.
    _inbuilt_functions = []
    _inbuilt_variables = []

    # clear the completions for the current file.
    def clear(self):
        self._functions = []
        self._variables = []

    # adds the class to _classes
    def add_class(self, class_name, parent_class, description, file_name):
        if self.get_class(class_name) is None:
            c = ClassReference(class_name, parent_class, description, file_name, self)
            self._classes.append(c)
            return c

    # links all classes together
    def link_classes(self):
        for c in self._classes:
            c.link_to_parent()

    # returns the found object inside out_of (self, class object)
    def get_object(self, word, out_of, b_no_classes=False, b_no_functions=False, b_no_variables=False, b_second_type=False):
        if not out_of:
            out_of = self
        if word[-1:] == ']':
            word = word.split('[')[0]
        elif b_second_type:
            b_second_type = False
        if isinstance(out_of, Struct):
            return out_of.get_variable(word)
        # don't try to get classes out of a class
        if not isinstance(out_of, ClassReference) and not b_no_classes:
            c = out_of.get_class(word)
            if c is not None:
                return c if not b_second_type else (c, True)
        if not b_no_functions:
            f = out_of.get_function(word)
            if f is not None:
                return f if not b_second_type else (f, True)
        if not b_no_variables:
            v = out_of.get_variable(word)
            if v is not None:
                return v if not b_second_type else (v, True)
        if isinstance(out_of, ClassReference):
            if not out_of.has_parsed():
                print "class ", out_of.name(), " not parsed yet, parse class now..."
                out_of.parse_me()
                return "parsing..."

        # Nothing found, search in the current view
        view = sublime.active_window().active_view()
        regex_var = r"(var|local)(\(\w*\))?\s([^\s]+)\s" + word
        regex_func = r"([a-zA-Z0-9()\s]*?)function[\s]+((coerce)\s*)?([a-zA-z0-9<>_]*?)[\s]*("+word+r")([\s]*\(+)(.*)((\s*\))+)[\s]*(const)?[\s]*;?[\s]*(\/\/.*)?"
        var = view.find(regex_var, 0, sublime.IGNORECASE)
        if var:
            var_lines = view.substr(var).split()[:-1]
            row, col = view.rowcol(var.a)
            return Variable(var_lines, word, "", row + 1, sublime.active_window().active_view().file_name(), "")
        func = view.find(regex_func, 0, sublime.IGNORECASE)
        if func:
            line = view.substr(func)
            row, col = view.rowcol(func.a)
            print line
            matches = re.search(regex_func, line)    # search for:  1: modifiers, 2: coerce, 3: ?, 4: return type, 5: name, ..,  7: arguments ...
            if matches:
                return Function(matches.group(1).strip(), matches.group(4).strip(), word, matches.group(7).strip(), row + 1, sublime.active_window().active_view().file_name(), "", True)
        return None

    # returns the type (class) of the object before the dot
    def get_class_from_context(self, line, from_class=None):
        # ! TODO: not entirely correct, doesn't work properly on foo(foo2.arg, foo3.arg2).
        #           => DONT split on a dot!
        objs = line[:-1].split('.')
        print objs, from_class.name() if from_class else ""
        # we're lucky, it's just one object, easy.
        if len(objs) == 1:
            if line[-5:] == "self.":
                active_file = sublime.active_window().active_view().file_name()
                return self.get_class_from_filename(active_file)

            if line[-6:] == "super.":
                active_file = sublime.active_window().active_view().file_name()
                # return self.get_class(self.get_class_from_filename(active_file).parent_class())
                return self.get_class_from_filename(active_file).get_parent()

            # something like 'super(Actor).' or 'Actor(controller).'
            if line[-2:] == ").":
                if "super(" in line:
                    return self.get_class(line.split('(')[-1][:-2])
                else:
                    # typecasting: something like Actor(controller)
                    # or a function with return value
                    obj = line.split('(')[0]
                    if from_class:
                        o = self.get_object(obj, from_class, b_second_type=True)
                    else:
                        o = self.get_object(obj, self, b_second_type=True)
                    if o == "parsing...":
                        return o
                    return self.get_object_type(o, from_class)
            # a single object
            else:
                obj = line[:-1]
                if from_class:
                    o = self.get_object(obj, from_class, b_no_classes=True, b_second_type=True)
                else:
                    o = self.get_object(obj, self, b_no_classes=True, b_second_type=True)
                if o == "parsing...":
                    return o
                return self.get_object_type(o, from_class)

        # (= more than one dot)
        else:
            # find class of the first object
            c = self.get_class_from_context(objs[0] + '.', from_class)
            if c == "parsing...":
                return c
            if c:
                # call itself with the found class and the other objects
                return self.get_class_from_context(".".join(objs[1:]) + '.', c)

    # returns the objects type (its class)
    def get_object_type(self, obj, its_class=None):
        b_second_type = False
        if isinstance(obj, tuple):
            obj = obj[0]
            b_second_type = True
        if isinstance(obj, Function):
            class_name = obj.return_type()
        elif isinstance(obj, Variable):
            class_name = obj.type() if not b_second_type else obj.secondary_type()
        elif isinstance(obj, ClassReference):
            return obj
        else:
            print "obj ", obj, " has no type!"
            return None
        if class_name:
            print "object type: ", class_name
            c = self.get_class(class_name)
            if c:
                return c
            s = self.get_object(class_name, its_class)
            return s
        return None

    # returns the class with the given name:
    def get_class(self, name):
        for _class in self._classes:
            if _class.name().lower() == name.lower():
                return _class
        return None

    # returns the class with the given filename
    def get_class_from_filename(self, filename):
        for _class in self._classes:
            if _class.file_name().lower() == filename.lower():
                return _class
        return None

    # returns the found function in _functions
    def get_function(self, name):
        for function in self._functions + self._inbuilt_functions:
            if isinstance(function, basestring):
                continue
            if function.function_name().lower() == name.lower():
                return function
        return None

    # returns the found variable in _variables
    def get_variable(self, name):
        for variable in self._variables + self._inbuilt_variables:
            if isinstance(variable, basestring):
                continue
            if variable.name().lower() == name.lower():
                return variable
        return None

# ==============================
# Completions
# ==============================

    # remove filename from _filenames
    # remove filename from _completions_for_file
    # remove completions from the class of this filename
    def remove_file(self, filename):
        for f in self._filenames[:]:
            if filename == f:
                self._filenames.remove(f)
                break
        for c in self._completions_for_file[:]:
            if filename == c[0]:
                self._completions_for_file.remove(c)
                break
        my_class = self.get_class_from_filename(filename)
        if my_class is not None:
            my_class.clear()

    # returns the current suggestions for this file.
    # if from_class is given, returns the completions for the given class
    def get_autocomplete_list(self, word, b_no_classes=False, b_no_functions=False, b_no_variables=False, from_class=None, bNoStandardCompletions=False):
        unsorted_autocomplete_list = []
        current_list = -1
        autocomplete_list = []
        b_no_built_in = False

        if from_class:
            b_no_built_in = True
            if from_class == "type not found":
                sublime.active_window().run_command("hide_auto_complete")
                return None
            functions, variables = self.get_completions_from_class(from_class)
            if functions == "parsing..." or variables == "parsing...":
                self.b_wanted_to_autocomplete = True
                return [("just a moment...", "")]
            # store the class for easy access later
            self.completion_class = from_class

        else:
            # ! TODO: add local variables
            functions = self._functions
            variables = self._variables
            if self._inbuilt_functions == []:
                self._inbuilt_functions, self._inbuilt_variables = self.get_completions_from_class(self.get_class("HiddenFunctions"))
                if self._inbuilt_functions == "parsing...":
                    self._inbuilt_functions = []
                    self._inbuilt_variables = []

        # filter relevant items:
        if not b_no_variables:
            for variable in variables + (self._inbuilt_variables if not b_no_built_in else []):
                if isinstance(variable, basestring):
                    current_list += 1
                    unsorted_autocomplete_list.append([(variable, "")])
                elif word.lower() in variable.name().lower():
                    unsorted_autocomplete_list[current_list].append((variable.name() + '\t' + variable.var_modifiers(), variable.name()))
                    # autocomplete_list.append((variable.name() + '\t' + variable.var_modifiers(), variable.name()))

        if not b_no_functions:
            for function in functions + (self._inbuilt_functions if not b_no_built_in else []):
                if isinstance(function, basestring):
                    current_list += 1
                    unsorted_autocomplete_list.append([(function, "")])
                elif word.lower() in function.function_name().lower():
                    function_str = function.function_name() + '\t(' + function.arguments() + ')'    # add arguments
                    unsorted_autocomplete_list[current_list].append((function_str, function.function_name()))
                    # autocomplete_list.append((function_str, function.function_name()))

        # sort
        for i in range(0, len(unsorted_autocomplete_list)/2):
            autocomplete_list += unsorted_autocomplete_list[i] + unsorted_autocomplete_list[i + len(unsorted_autocomplete_list)/2]

        if not b_no_classes:
            for _class in self._classes:
                if word.lower() in _class.name().lower():
                    autocomplete_list.append((_class.name() + '\t' + "Class", _class.name()))

        if bNoStandardCompletions:
            return autocomplete_list, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS
        else:
            return autocomplete_list

    # returns all completions for a class and all its parent classes.
    # takes a filename as an argument or a class reference
    # return ("parsing...", "parsing...") if the class wasn't parsed before
    def get_completions_from_class(self, class_file_name):
        if isinstance(class_file_name, Struct):
            return ([""], ["### " + class_file_name.name() + "\t-    Variables ###"] + class_file_name.get_variables())
        elif isinstance(class_file_name, ClassReference):
            my_class = class_file_name
        else:
            my_class = self.get_class_from_filename(class_file_name)
        if my_class:
            if my_class.has_parsed():
                return (self.get_functions_from_class(my_class), self.get_variables_from_class(my_class))
            else:
                my_class.parse_me()
                return ("parsing...", "parsing...")
        else:
            print "No class found for ", class_file_name

    # returns all functions from the given class and all its parent classes
    def get_functions_from_class(self, my_class):
        functions = []
        functions.append("### " + my_class.name() + "\t-    Functions ###")
        functions += my_class.get_functions()

        # parent_file = self.get_class(my_class.parent_class())
        parent_file = my_class.get_parent()
        if parent_file is None:
            return functions

        functions += self.get_functions_from_class(parent_file)
        return functions

    # returns all variables from the given class and all its parent classes
    def get_variables_from_class(self, my_class):
        variables = []
        variables.append("### " + my_class.name() + "\t-    Variables ###")
        variables += my_class.get_variables()

        # parent_file = self.get_class(my_class.parent_class())
        parent_file = my_class.get_parent()
        if parent_file is None:
            return variables

        variables += self.get_variables_from_class(parent_file)
        return variables

    # saves all completions to a file.
    # ! TODO: have a look at comment for _completions_for_file
    def save_completions_to_file(self, filename):
        names = [x[0] for x in self._completions_for_file]
        if filename not in names:
            self._completions_for_file.append((filename, self._functions, self._variables))

    # loads all completions for a file
    def load_completions_for_file(self, filename):
        for c in self._completions_for_file:
            if filename == c[0]:
                self._functions = c[1]
                self._variables = c[2]
                break


# -------------------------------------
# Classes, Functions and Variables
# -----------------
#
# These can create dynamic tool-tips and dynamic snippets based on their content
# ___________________________________

# stores classes
# every class can also store all functions and variables that are inside this class
class ClassReference:
    def __init__(self, class_name, parent_class, description, file_name, collector_reference):
        self._name = class_name
        self._description = description
        self._file_name = file_name
        self._parent_class_name = parent_class
        self._collector_reference = collector_reference
        self._child_classes = []
        self._functions = []
        self._variables = []
        self._consts = []
        self._structs = []
        self._b_was_parsed = False
        self._parent_class = None

    def description(self):
        return self._description

    def name(self):
        return self._name

    def line_number(self):
        return 1

    def file_name(self):
        return self._file_name

    def link_to_parent(self):
        self._parent_class = self._collector_reference.get_class(self._parent_class_name)
        if self._parent_class:
            self._parent_class.set_child(self)

    def set_child(self, child):
        # print "link: ", child.name(), "  to: ", self.name()
        self._child_classes.append(child)

    def remove_child(self, child):
        self._child_classes.remove(child)

    def children(self):
        return self._child_classes

    def get_parent(self):
        return self._parent_class

    def parent_class(self):
        return self._parent_class_name

    def has_parsed(self):
        return self._b_was_parsed

    def save_completions(self, functions, variables, consts, structs):
        self._variables = variables
        self._functions = functions
        self._consts = consts
        self._structs = structs
        self._b_was_parsed = True

    def clear(self):
        self._functions = []
        self._variables = []
        self._consts = []
        self._structs = []
        self._b_was_parsed = False

    # returns all _functions that were stored inside this class. To make sure it was parsed before, use has_parsed()
    def get_functions(self):
        return self._functions

    def get_function(self, name):
        for f in self._functions:
            if name.lower() == f.function_name().lower():
                return f
        p_class = self._collector_reference.get_class(self._parent_class_name)
        if p_class is not None:
            return p_class.get_function(name)
        return None

    def get_variables(self):
        return self._variables + self._consts + self._structs

    def get_variable(self, name):
        for v in self._variables:
            if name.lower() == v.name().lower():
                return v
        for s in self._structs:
            if name.lower() == s.name().lower():
                return s
        for c in self._consts:
            if name.lower() == c.name().lower():
                return c
        p_class = self._collector_reference.get_class(self._parent_class_name)
        if p_class is not None:
            return p_class.get_variable(name)
        return None

    def set_collector_reference(self, collector_reference):
        self._collector_reference = collector_reference

    def update_class(self, parent_class_name, description):
        p = self.get_parent()
        if p:
            self.get_parent().remove_child(self)
        self._parent_class_name = parent_class_name
        self._description = description
        self.link_to_parent()

    def parse_me(self):
        view = sublime.active_window().active_view()
        self._collector_reference.add_function_collector_thread(self._file_name)  # create a new thread to search for relevant functions for this class
        self._collector_reference.handle_threads(self._collector_reference._collector_threads, view)  # display progress bar

    def insert_dynamic_snippet(self, view):
        self.create_dynamic_tooltip(view)
        view.run_command("insert_snippet", {"contents": (Object_Name % {"name": self._name})})

    def create_dynamic_tooltip(self, view):
        documentation = self.description()
        print_to_panel(view, documentation)


class Struct:
    _variables = []

    def __init__(self, struct_name, struct_line, line_number, file_name, description):
        self._name = struct_name
        self._description = description
        self._file_name = file_name
        self._struct_line = struct_line
        self._line_number = line_number

    def description(self):
        return self._description

    def declaration(self):
        return self._struct_line

    def name(self):
        return self._name

    def var_modifiers(self):
        return "Struct"

    def line_number(self):
        return self._line_number

    def file_name(self):
        return self._file_name

    def save_variables(self, variables):
        self._variables = variables

    def get_variables(self):
        return self._variables

    def get_variable(self, name):
        for v in self._variables:
            if name.lower() == v.name().lower():
                return v
        return None

    def insert_dynamic_snippet(self, view):
        self.create_dynamic_tooltip(view)
        view.run_command("insert_snippet", {"contents": (Object_Name % {"name": self._name})})

    def create_dynamic_tooltip(self, view):
        documentation = self.description()
        print_to_panel(view, documentation + self._struct_line)


# class to store a function / event
class Function:
    def __init__(self, function_modifiers, return_type, function_name, arguments, line_number, file_name, description, is_funct):
        self._function_modifiers = function_modifiers
        self._return_type = return_type
        self._function_name = function_name
        self._arguments = arguments
        self._line_number = line_number
        self._file_name = file_name
        self._description = description
        self._b_is_function = is_funct

    def function_modifiers(self):
        if self._function_modifiers != "":
            return self._function_modifiers + " "
        return ""

    def return_type(self, b_pretty=False):
        if b_pretty and self._return_type != "":
            return " " + self._return_type
        return self._return_type

    def function_name(self):
        return self._function_name

    def declaration(self):
        return self.function_modifiers() + ("function" if self._b_is_function == 1 else "event") + self.return_type() + self.function_name() + "(" + self.arguments() + ")"

    def arguments(self):
        return self._arguments

    def line_number(self):
        return self._line_number

    def file_name(self):
        return self._file_name

    def description(self):
        if self._description == "":
            return self.declaration()
        return self._description

    def documentation(self):
        doc = ""
        for line in self._description.split('\n'):
            if line.lstrip() != "" and (line.lstrip()[0] == "/" or line.lstrip()[0] == "*"):
                doc += line + "\n"
        return doc

    # ! (TODO): not properly formatted. I should remove white space first.
    #   Better: save it properly, e.g. modify the save_functions method
    def insert_dynamic_snippet(self, view):
        self.create_dynamic_tooltip(view)

        if view.rowcol(view.sel()[0].begin())[1] == 0:  # if run from the beginning of the line, assume it's a declaration
            # get arguments without the type
            less_arguments = ""
            if self._arguments != "":
                less_args = self._arguments.split(',')

                for arg in less_args:
                    less_arguments += arg.split()[-1] + ", "
                less_arguments = less_arguments[:-2]

            # add a tabstop for description
            # description = ""
            # if self.documentation() != "":
            #     description = '${1:' + self.documentation() + '}'

            view.run_command("insert_snippet",
                            {"contents": (Function_Snippet_Declaration % {  "function_modifiers": self.function_modifiers(),
                                                                            "return_type": self.return_type(True),
                                                                            "function_name": self._function_name,
                                                                            "arguments": self._arguments,
                                                                            # "description": description,
                                                                            "funct": "function" if self._b_is_function == 1 else "event",
                                                                            "less_arguments": less_arguments})})
        else:
            less_args = self._arguments.split(',')
            arguments = ""
            # end_position = 1
            if len(less_args) > 0 and less_args[0] != "":
                for i in range(len(less_args)):
                    arguments += '${' + str(i + 1) + ':' + less_args[i] + '}'
                    # end_position += 1
                    if len(less_args) != (i + 1):
                        arguments += ", "
            # end_stop = '${' + str(end_position) + ':;}'
            view.run_command("insert_snippet", {"contents": (Function_Snippet_Call % {"function_name": self._function_name, "arguments": arguments})})  # , "end_stop": end_stop

    def create_dynamic_tooltip(self, view):
        # documentation = self.description() + self.function_modifiers() + ("function" if self._b_is_function == 1 else "event") + self.return_type() + self.function_name() + "(" + self.arguments() + ")"
        print_to_panel(view, self.description())


# stores variables
class Variable:
    def __init__(self, var_modifiers, var_name, comment, line_number, file_name, description=""):
        self._variable_modifiers = var_modifiers
        self._name = var_name
        self._description = description
        self._comment = comment
        self._line_number = line_number
        self._file_name = file_name

    def var_modifiers(self):
        return ' '.join(self._variable_modifiers) + ' '

    def type(self):
        v_type = self._variable_modifiers[-1].strip()
        if "class<" == v_type[:6].lower():
            v_type = "class"
        elif "array<" == v_type[:6].lower():
            v_type = "array"
        return v_type

    def secondary_type(self):
        v_type = self._variable_modifiers[-1].strip()
        if "class<" == v_type[:6].lower():
            v_type = v_type[6:-1].strip()
        elif "array<" == v_type[:6].lower():
            v_type = v_type[6:-1].strip()
        return v_type

    def comment(self):
        return self._comment

    def name(self):
        return self._name

    def declaration(self):
        return self.var_modifiers() + self.name() + ";" + (" //" + self.comment() if self.comment() != "" else "")

    def line_number(self):
        return self._line_number

    def file_name(self):
        return self._file_name

    def description(self):
        return self._description

    def insert_dynamic_snippet(self, view):
        self.create_dynamic_tooltip(view)
        view.run_command("insert_snippet", {"contents": (Object_Name % {"name": self._name})})

    def create_dynamic_tooltip(self, view):
        documentation = self.description()
        if documentation.strip() == "":
            documentation = self.declaration()
        print_to_panel(view, documentation)


# stores CONST
class Const:
    def __init__(self, CONST_name, value, comment, line_number, file_name, description=""):
        self._name = CONST_name
        self._value = value
        self._description = description
        self._comment = comment
        self._line_number = line_number
        self._file_name = file_name

    def type(self):
        return None

    def value(self):
        return self._value

    def var_modifiers(self):
        return "CONST = " + self.value()

    def comment(self):
        if self._comment.strip() == "":
            return ""
        return "    // " + self._comment

    def name(self):
        return self._name.strip()

    def declaration(self):
        return self.description()

    def line_number(self):
        return self._line_number

    def file_name(self):
        return self._file_name

    def description(self):
        return self._description

    def insert_dynamic_snippet(self, view):
        self.create_dynamic_tooltip(view)
        view.run_command("insert_snippet", {"contents": (Object_Name % {"name": self._name})})

    def create_dynamic_tooltip(self, view):
        documentation = "const " + self.name() + " = " + self.value() + ";" + self.comment()
        print_to_panel(view, documentation)


# --------------------------------
# Dynamic Snippets
# ----------------

Function_Snippet_Declaration = \
"""%(function_modifiers)s%(funct)s%(return_type)s %(function_name)s(%(arguments)s)
{
    ${2:super.%(function_name)s(%(less_arguments)s);}
    ${3://}
}"""

Function_Snippet_Call = \
"""%(function_name)s(%(arguments)s)"""

Object_Name = \
"""%(name)s"""