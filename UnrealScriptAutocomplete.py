#-----------------------------------------------------------------------------------
# UnrealScript Auto-complete Plug-in
#-----------------------------------------------------------------------------------
#	This plug in displays UnrealScript Functions with parameters.
#   It searches in all parent classes of the current class.
#   Uses context sensitive completions.
#
#   TODO:
#       -autocomplete classes after expand
#       -variable read in error: var bool bOne, bTwo, bTrhee; doesn't work yet
#       -problematic function declaration:
#           native(548) noexport final function bool FastTrace
#           (
#               vector          TraceEnd,
#               optional vector TraceStart,
#               optional vector BoxExtent,
#               optional bool   bTraceBullet
#           );
#       -load auto complete suggestions from current object before a '.'
#       -same for goto definition
#
# (c) Florian Zinggeler
#-----------------------------------------------------------------------------------
import sublime
import sublime_plugin
import threading
import os
import re


functions_reference, variables_reference, classes_reference = [], [], []
last_location = None
current_location = None


# how many seconds the help panel will stay up
OPEN_TIME = 10


def print_to_panel(view, text):
    panel = view.window().get_output_panel('UnrealScriptAutocomplete_panel')
    panel_edit = panel.begin_edit()
    panel.insert(panel_edit, panel.size(), text)
    panel.end_edit(panel_edit)
    panel.show(panel.size())
    view.window().run_command("show_panel", {"panel": "output.UnrealScriptAutocomplete_panel"})


class HelperObject:
    pending_modification = 0

    def hide_panel(self, view):
        self.pending_modification -= 1
        if self.pending_modification <= 0:
            self.pending_modification = 0
            try:
                view.window().run_command("hide_panel", {"panel": "output.UnrealScriptAutocomplete_panel"})
            except AttributeError:
                print "'NoneType' object has no attribute 'run_command'"


class UnrealGotoDefinitionCommand(sublime_plugin.TextCommand, HelperObject):
    def run(self, edit):
        active_file = self.view.file_name()
        if is_unrealscript_file(active_file):
            region_word = self.view.word(self.view.sel()[0])
            word = self.view.substr(region_word)
            window = sublime.active_window()

            global last_location, current_location
            if last_location != None:
                if current_location == active_file:
                    window.open_file(last_location, sublime.ENCODED_POSITION)
                    window.open_file(last_location, sublime.ENCODED_POSITION)
                    last_location = None
                    return
                last_location = None

            # Save current position so we can return to it
            row, col = self.view.rowcol(self.view.sel()[0].begin())
            last_location = "%s:%d" % (active_file, row + 1)

            function = self.get_function(word)
            if function != None:
                if os.path.exists(function.file_name()):
                    window.open_file(function.file_name() + ':' + str(function.line_number()) + ':0', sublime.ENCODED_POSITION | sublime.TRANSIENT)     # somehow calling this twice fixes a bug that makes sublime crash...
                    window.open_file(function.file_name() + ':' + str(function.line_number()) + ':0', sublime.ENCODED_POSITION | sublime.TRANSIENT)
                    current_location = function.file_name()
                else:
                    print function.file_name() + 'does not exist'
                return
            variable = self.get_variable(word)
            if variable != None:
                if os.path.exists(variable.file_name()):
                    window.open_file(variable.file_name() + ':' + str(variable.line_number()) + ':0', sublime.ENCODED_POSITION | sublime.TRANSIENT)
                    window.open_file(variable.file_name() + ':' + str(variable.line_number()) + ':0', sublime.ENCODED_POSITION | sublime.TRANSIENT)
                    current_location = variable.file_name()
                else:
                    print variable.file_name() + 'does not exist'
                return
            _class = self.get_class(word)
            if _class != None:
                if os.path.exists(_class[1]):
                    window.open_file(_class[1] + ":1:0", sublime.ENCODED_POSITION | sublime.TRANSIENT)
                    window.open_file(_class[1] + ":1:0", sublime.ENCODED_POSITION | sublime.TRANSIENT)
                    current_location = _class[1]
                else:
                    print _class[1] + 'does not exist'
                return
            print_to_panel(self.view, word + " not found")
            sublime.set_timeout(lambda: self.hide_panel(self.view), OPEN_TIME * 1000)

    def get_function(self, name):
        global functions_reference
        for function in functions_reference:
            if function.function_name() == name:
                return function
        return None

    def get_variable(self, name):
        global variables_reference
        for variable in variables_reference:
            if variable.name() == name:
                return variable
        return None

    # (class_name, class_path, description)
    def get_class(self, name):
        global classes_reference
        for _class in classes_reference:
            if _class[0].lower() == name.lower():
                return _class
        return None


# base class for adding new auto-complete suggestions
class UnrealScriptAutocomplete:
    # stores all functions and information about them
    _functions = []
    # store all variables
    _variables = []
    # store all parent classes and information. (class_name, class_path, description)
    _classes = []
    # stores all functions to use on a file
    _functions_for_file = []

    def clear(self):
        self._functions = []
        self._variables = []
        self._classes = []

    def add_func(self, function_modifiers, return_type, function_name, arguments, line_number, file_name, description="", is_funct=1):
        if self.get_function(function_name) == None:
            self._functions.append(Function(function_modifiers, return_type, function_name, arguments, line_number + 1, file_name, description, is_funct))

    def add_var(self, var_modifiers, var_name, comment, line_number, file_name, description=""):
        if self.get_variable(var_name) == None:
            self._variables.append(Variable(var_modifiers, var_name, comment, line_number + 1, file_name, description=""))

    def get_function(self, name):
        for function in self._functions:
            if function.function_name() == name:
                return function
        return None

    def get_variable(self, name):
        for variable in self._variables:
            if variable.name() == name:
                return variable
        return None

    def save_functions_to_list(self, filename):
        names = [x[1] for x in self._functions_for_file]

        if filename not in names:
            self._functions_for_file.append((self._functions, filename, self._variables, self._classes))

    def get_autocomplete_list(self, word, b_only_var=False):
        autocomplete_list = []
        for variable in self._variables:
            if word in variable.name():
                autocomplete_list.append((variable.name(), variable.name()))
        if not b_only_var:
            for function in self._functions:
                if word in function.function_name():
                    function_str = function.function_name() + '\t(' + function.arguments() + ')'    # add arguments
                    autocomplete_list.append((function_str, function.function_name()))

        return autocomplete_list


# Creates threads for collecting any function, event or variable in the project folder that is relevant. e.g. collects from parent classes.
class FunctionsCollector(UnrealScriptAutocomplete, sublime_plugin.EventListener, HelperObject):
    # active threads
    _collector_threads = []
    # files that have already been parsed
    _filenames = []

    b_did_autocomplete = False

    # clear functions for current file
    # def on_close(self, view):
    #     pass

    def on_post_save(self, view):  # gets called when a file is saved. reset everything
        if view.file_name() != None and is_unrealscript_file(view.file_name()):
            self.clear_all()
            self.on_activated(view)

    # start parsing when a tab becomes active
    def on_activated(self, view):
        self.clear()    # empty the function list, so that we only get the relevant ones.

        if view.file_name() != None and is_unrealscript_file(view.file_name()):
            open_folder_arr = view.window().folders()   # Gets all opened folders in the Sublime Text editor.

            if view.file_name() not in self._filenames:     # if the wasn't parsed before
                self._filenames.append(view.file_name())
                self.add_thread(view.file_name(), open_folder_arr)  # create a new thread to search for relevant functions for the active file

            else:
                # print("already parsed")
                names = [x[1] for x in self._functions_for_file]
                for i, name in enumerate(names):
                    if view.file_name() == name:    # get the functions we saved for the current file
                        self._functions = self._functions_for_file[i][0]
                        self._variables = self._functions_for_file[i][2]
                        self._classes = self._functions_for_file[i][3]
                        global functions_reference, variables_reference, classes_reference
                        functions_reference = self._functions
                        variables_reference = self._variables
                        classes_reference = self._classes

            self.handle_threads(self._collector_threads, view)  # display progress bar

    # This function is called when auto-complete pop-up box is displayed and this function returns an array with tuples:
    # [('<label>', '<text-to-paste>'),......]
    def on_query_completions(self, view, prefix, locations):
        current_file = view.file_name()
        completions = []

        if current_file != None and is_unrealscript_file(current_file):
            # if is in defaultproperties, only get variables:
            line_number = 1000000
            with open(current_file, 'rU') as file_lines:
                for i, line in enumerate(file_lines):
                    if "defaultproperties" in line.lower():
                        line_number = i + 1
                        break
            (row, col) = view.rowcol(view.sel()[0].begin())
            if row > line_number:
                return self.get_autocomplete_list(prefix, True)
            else:
                return self.get_autocomplete_list(prefix)

        return (completions, sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    # called right before auto completion.
    def on_query_context(self, view, key, operator, operand, match_all):
        current_file = view.file_name()
        if current_file != None and is_unrealscript_file(current_file):
            if key == "advanced_new_file_completion":
                region = view.sel()[0]
                if region.empty():
                    self.b_did_autocomplete = True

    # remove auto completion and insert dynamic snippet instead, just after auto completion
    def on_modified(self, view):
        current_file = view.file_name()

        if current_file != None and is_unrealscript_file(current_file):
            if self.b_did_autocomplete:
                self.b_did_autocomplete = False

                region_word = view.word(view.sel()[0])
                word = view.substr(region_word)

                if not all(c.isspace() for c in word):  # only if the current word doesn't contain any whitespace character
                    f = self.get_function(word)
                    v = self.get_variable(word)
                    if f or v:
                        edit = view.begin_edit('UnrealScriptAutocomplete')
                        view.replace(edit, region_word, "")     # remove last word
                        view.end_edit(edit)
                        if f:
                            f.insert_dynamic_snippet(view)    # insert snippet instead
                            sublime.set_timeout(lambda: self.hide_panel(view), OPEN_TIME * 1000)
                            self.pending_modification += 1
                        elif v:
                            v.insert_dynamic_snippet(view)
                            sublime.set_timeout(lambda: self.hide_panel(view), OPEN_TIME * 1000)
                            self.pending_modification += 1

    # creates a thread to parse the given file_name and all its parent classes
    def add_thread(self, file_name, open_folder_arr):
        self._collector_threads.append(FunctionsCollectorThread(self, file_name, 30, open_folder_arr))
        self._collector_threads[-1].start()

    def handle_threads(self, threads, view, i=0, dir=1):
        for thread in threads:
            if not thread.isAlive():
                threads.remove(thread)

        if len(threads):
            # This animates a little activity indicator in the status area
            before = i % 8
            after = (7) - before
            if not after:
                dir = -1
            if not before:
                dir = 1
            i += dir
            view.set_status('UnrealScriptAutocomplete', 'UnrealScriptAutocomplete is Parsing [%s=%s]' % \
                (' ' * before, ' ' * after))

            sublime.set_timeout(lambda: self.handle_threads(threads, view, i, dir), 100)
            return
        else:
            #finished and keep functions for later use
            self.save_functions_to_list(view.file_name())
            view.erase_status('UnrealScriptAutocomplete')
            global functions_reference, variables_reference, classes_reference
            functions_reference = self._functions
            variables_reference = self._variables
            classes_reference = self._classes

    def clear_all(self):
        self._functions_for_file = []
        self._filenames = []


# create a new thread for scanning one file, as this may take a while.
class FunctionsCollectorThread(threading.Thread):
    def __init__(self, collector, filename, timeout_seconds, open_folder_arr):
        self.collector = collector
        self.timeout = timeout_seconds
        self.filename = filename
        self.open_folder_arr = open_folder_arr
        threading.Thread.__init__(self)

    def run(self):  # gets called when the thread is created
        if self.filename != None:
            self.save_functions(self.filename)  # parse current file

        file_lines = open(self.filename, 'rU')
        description = ""

        for line in file_lines:
            description += line
            classline = re.match(r'(class\b.+\bextends )(\b.+\b)', line.lower())  # get class declaration line of current file
            if classline != None:
                parent_class_name = classline.group(2)    # get parent class

                # search open folders for parent class file
                for folder in self.open_folder_arr:
                    parent_file = self.search_file(folder, parent_class_name)
                    self.collector._classes.append((parent_class_name, parent_file, description))
                    if parent_file != None:
                        self.save_functions(parent_file)
                        self.collector.add_thread(parent_file, self.open_folder_arr)    # create a new thread to do the same stuff on the parent_file
                    else:
                        print "parent file not found in: ", folder
                break

        self.stop()

    # search for the given file (file_name) in the given path (path). Returns the found file.
    def search_file(self, path, file_name):
        for file in os.listdir(path):
            dirfile = os.path.join(path, file)
            if os.path.isfile(dirfile):
                fileName, fileExtension = os.path.splitext(dirfile)

                if file_name.lower() + ".uc" == file.lower():
                    return dirfile

            elif os.path.isdir(dirfile):
                match = self.search_file(dirfile, file_name)
                if match != None:
                    return match

    # extract functions, event and variables (TODO: STRUCTS, ENUMS, CONST) and split them into smaller groups.
    def save_functions(self, file_name):
        with open(file_name, 'rU') as file_lines:
            current_documentation = ""

            for i, line in enumerate(file_lines):
                if "/**" in line or "//" in line:
                    current_documentation = line

                if "function" in line.lower():  # get possible lines containing functions
                    function_matches = re.search(r'(.*)\bfunction \b(\b.*\b)(.+)\((.*)\)', line)		# search for:  1: function modifiers, 2: return type, 3: function name, 4: arguments
                    if function_matches != None:
                        if function_matches.group(3) == None or function_matches.group(3) == " ":
                            pass
                            #print "not a real function!!! ", line   # some wrong lines
                        else:
                            self.collector.add_func(function_matches.group(1), function_matches.group(2), function_matches.group(3), function_matches.group(4), i, file_name, current_documentation)
                            current_documentation = ""

                elif "var" in line.lower():  # get possible lines containing variables
                    # 1: vartype, 2: name, 3: documentation
                    var_doc_line = line.split('//')
                    var_line = var_doc_line[0].split()
                    if var_line and "var" not in var_line[0]:
                        continue
                    elif not var_line:
                        continue

                    doc_line = ''
                    if len(var_doc_line) > 1:
                        doc_line = var_doc_line[1].rstrip()

                    var_names = []
                    var_names.append(var_line.pop().rstrip('\n\r\t ;'))     # get the right most variable
                    for v in var_line:
                        if "," in var_line[-1]:     # if there are multiple variable names in one line separated by ',' , get them.
                            var_names.append(var_line.pop().rstrip('\n\r\t ,'))
                        else:
                            break
                    for name in var_names:
                        self.collector.add_var(var_line, name, doc_line, i, file_name, current_documentation)
                    current_documentation = ""

                elif "event" in line.lower():
                    event_matches = re.search(r'(.*)\bevent \b(\b.*\b)(.+)\((.*)\)', line)        # search for:  1: event modifiers, 2: return type, 3: event name, 4: arguments
                    if event_matches != None:
                        if event_matches.group(3) == None or event_matches.group(3) == " ":
                            pass
                            # print "not a real event!!! ", line   # some wrong lines
                        else:
                            self.collector.add_func(event_matches.group(1), event_matches.group(2), event_matches.group(3), event_matches.group(4), i, file_name, current_documentation, 0)
                            current_documentation = ""

                if "/**" in current_documentation:
                    if current_documentation != line:
                        current_documentation += line

    def stop(self):
        if self.isAlive():
            self._Thread__stop()


def is_unrealscript_file(filename):
    return '.uc' in filename


# class to store a function/ event
class Function:
    # _function_modifiers = "" # _return_type = "" # _function_name = "" # _arguments = "" # _line_number = -1 # _file_name = "" # _description = "" # _b_is_function = -1

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
        return self._function_modifiers

    def return_type(self):
        return self._return_type

    def function_name(self):
        return self._function_name

    def arguments(self):
        return self._arguments

    def line_number(self):
        return self._line_number

    def file_name(self):
        return self._file_name

    def description(self):
        return self._description

    def insert_dynamic_snippet(self, view):
        self.create_dynamic_tooltip(view)
        less_arguments = ""

        if self._arguments != "":
            less_args = self._arguments.split(' ')
            less_arguments = ""

            for i, arg in enumerate(less_args):
                if (i + 1) % 2 == 0:
                    less_arguments += arg + " "

            less_arguments, t = less_arguments[:-1], less_arguments[-1]

        if view.rowcol(view.sel()[0].begin())[1] == 0:  # if run from the beginning of the line, assume it's a declaration
            description = ""
            if self._description != "":
                description = '${1:' + self._description + '}'
            view.run_command("insert_snippet",
                            {"contents": (Function_Snippet_Declaration % {"function_modifiers": self._function_modifiers,
                                                                            "return_type": self._return_type,
                                                                             "function_name": self._function_name,
                                                                             "arguments": self._arguments,
                                                                             "description": description,
                                                                             "funct": "function" if self._b_is_function == 1 else "event",
                                                                             "less_arguments": less_arguments})})
        else:
            less_args = self._arguments.split(',')
            arguments = ""
            end_position = 1
            if len(less_args) > 0 and less_args[0] != "":
                for i in range(len(less_args)):
                    arguments += '${' + str(i + 1) + ':' + less_args[i] + '}'
                    end_position += 1
                    if len(less_args) != (i + 1):
                        arguments += ", "
            end_stop = '${' + str(end_position) + ':;}'
            view.run_command("insert_snippet", {"contents": (Function_Snippet_Call % {"function_name": self._function_name, "arguments": arguments, "end_stop": end_stop})})

    def create_dynamic_tooltip(self, view):
        documentation = self.description() + self.function_modifiers() + self.return_type() + ("function" if self._b_is_function == 1 else "event") + self.function_name() + "(" + self.arguments() + ")"
        print_to_panel(view, documentation)


# stores variables
class Variable:
    # _variable_modifiers = "" # _name = "" # _description = "" # _comment = "" # _file_name = "" # _line_number = -1

    def __init__(self, var_modifiers, var_name, comment, line_number, file_name, description=""):
        self._variable_modifiers = var_modifiers
        self._name = var_name
        self._description = description
        self._comment = comment
        self._line_number = line_number
        self._file_name = file_name

    def var_modifiers(self):
        return ' '.join(self._variable_modifiers) + ' '

    def comment(self):
        return self._comment

    def name(self):
        return self._name

    def line_number(self):
        return self._line_number

    def file_name(self):
        return self._file_name

    def description(self):
        return self._description

    def insert_dynamic_snippet(self, view):
        self.create_dynamic_tooltip(view)
        if view.rowcol(view.sel()[0].begin())[1] == 0:  # if run from the beginning of the line, assume it's a declaration
            description, comment = "", ""
            if self._description != "":
                description = '${1:' + self._description + '}'
            if self._comment != "":
                comment = ' //' + self._comment

            view.run_command("insert_snippet", {"contents": (Variable_Snippet_Declaration % {"description": description, "var_modifiers": self.var_modifiers(), "name": self._name, "comment": comment})})

        else:
            view.run_command("insert_snippet", {"contents": (Variable_Snippet_Name % {"name": self._name})})

    def create_dynamic_tooltip(self, view):
        documentation = self.description() + self.var_modifiers() + self.name() + ";" + (" //" + self.comment() if self.comment() != "" else "")
        print_to_panel(view, documentation)


Function_Snippet_Declaration = \
"""%(description)s%(function_modifiers)s%(return_type)s%(funct)s %(function_name)s(%(arguments)s)
{
    ${2:super.%(function_name)s(%(less_arguments)s);}
    ${3://}
}
"""

Function_Snippet_Call = \
"""%(function_name)s(%(arguments)s)%(end_stop)s
"""

Variable_Snippet_Declaration = \
"""%(description)s%(var_modifiers)s%(name)s;%(comment)s
"""

Variable_Snippet_Name = \
"""%(name)s"""
