#-----------------------------------------------------------------------------------
# UnrealScriptIDE Auto-complete Plug-in
#-----------------------------------------------------------------------------------
#	This plug-in displays UnrealScript Functions with parameters.
#   It searches in all parent classes of the current class.
#   Uses context sensitive completions.
#
#   TODO:
#       -autocomplete classes after extends
#       -save all classes (name, file_name, description) when first UnrealScript file is opened:
#           store in _classes, don't clear them
#           optimize search file by using the new _classes
#           create a class for _classes
#           use classes in autocompletion suggestions and display description
#
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


# stores the currently used completions for this file. needed for Goto Declaration
functions_reference, variables_reference, classes_reference = [], [], []

last_location = None
current_location = None


# how many seconds the help panel will stay up
OPEN_TIME = 10


# prints the text to the "helper panel" (Actually the console)
def print_to_panel(view, text):
    panel = view.window().get_output_panel('UnrealScriptAutocomplete_panel')
    panel_edit = panel.begin_edit()
    panel.insert(panel_edit, panel.size(), text)
    panel.end_edit(panel_edit)
    panel.show(panel.size())
    view.window().run_command("show_panel", {"panel": "output.UnrealScriptAutocomplete_panel"})


# only used to hide the panel. The hide_panel doesn't work as a global function, so this is a workaround
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


# opens the definition of the current selected word.
#  - if b_new_start_point is true, the current cursor position will be stored.
class UnrealGotoDefinitionCommand(sublime_plugin.TextCommand, HelperObject):
    def run(self, edit, b_new_start_point=False):
        active_file = self.view.file_name()

        if is_unrealscript_file(active_file):
            region_word = self.view.word(self.view.sel()[0])
            word = self.view.substr(region_word)
            window = sublime.active_window()

            global last_location, current_location

            # if no word is selected or the cursor is at the beginning of the line, return to last location
            row, col = self.view.rowcol(self.view.sel()[0].begin())
            if last_location is not None and (word.strip() == "" or col == 0):
                if current_location.lower() == active_file.lower():
                    window.open_file(last_location, sublime.ENCODED_POSITION)
                    window.open_file(last_location, sublime.ENCODED_POSITION)
                    last_location = None
                    return

            # ! TODO:   adapt to class object.
            #           get line and check if it has a '.' before the variable
            # search the current word in functions, variables and classes and if found, open the file.
            _class = self.get_class(word)
            if _class is not None:
                self.open_file(_class[1], 1, b_new_start_point)
                return

            function = self.get_function(word)
            if function is not None:
                self.open_file(function.file_name(), function.line_number(), b_new_start_point)
                return

            variable = self.get_variable(word)
            if variable is not None:
                self.open_file(variable.file_name(), variable.line_number(), b_new_start_point)
                return

            # if the word wasn't found:
            self.view.set_status('UnrealScriptGotoDefinition', '"' + word + '" not found!')

        elif is_unreal_log_file(active_file):
            line = self.view.substr(self.view.line(self.view.sel()[0]))
            split_line = re.split(r"\(|\)", line)   # line.split("()")
            if len(split_line) > 1:
                self.open_file(split_line[0], split_line[1], True)
            else:
                self.view.set_status('UnrealScriptGotoDefinition', '"' + line + '" not found!')

    # opens the file (file_name) at (line_number). If b_new_start_point is true, save the current position.
    def open_file(self, file_name, line_number=1, b_new_start_point=False):
        global last_location, current_location
        active_file = self.view.file_name()
        window = sublime.active_window()

        # save position, if we either didn't save any before, or b_new_start_point is set to true
        if last_location is None or b_new_start_point:
            # Save current position so we can return to it
            row, col = self.view.rowcol(self.view.sel()[0].begin())
            last_location = "%s:%d" % (active_file, row + 1)

        if os.path.exists(file_name):
            # somehow calling this twice fixes a bug that makes sublime crash, no idea why though...
            window.open_file(file_name + ':' + str(line_number) + ':0', sublime.ENCODED_POSITION | sublime.TRANSIENT)
            window.open_file(file_name + ':' + str(line_number) + ':0', sublime.ENCODED_POSITION | sublime.TRANSIENT)
            current_location = file_name
        else:
            self.view.set_status('UnrealScriptGotoDefinition', '"' + file_name + '" does not exist!')

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

    # ! TODO: change to class object.
    # (class_name, class_path, description)
    def get_class(self, name):
        global classes_reference
        for _class in classes_reference:
            if _class[0].lower() == name.lower():
                return _class
        return None

#================================================================================
#================Autocompletion==================================================
#================================================================================


# base class for adding new auto-complete suggestions
class UnrealScriptAutocomplete:
    # stores all functions and information about them
    _functions = []
    # store all variables
    _variables = []
    # ! TODO: use classes object
    # store all classes (not just parent classes)
    # - at the beginning search trough the whole source folder and fill this
    _classes = []
    # old (stores all functions, variables and classes to use on a file)
    # ! TODO: Maybe make an object for this?
    #  - this should actually hold a copy of _functions and _variables to use on one specific file (without the information from parent classes)
    _completions_for_file = []

    # clear the completions for the current file. To reset, use clear_all
    def clear(self):
        self._functions = []
        self._variables = []
        # ! NEW changed: _classes should remain on all files, because they are always relevant
        # self._classes = []

    def add_func(self, function_modifiers, return_type, function_name, arguments, line_number, file_name, description="", is_funct=1):
        if self.get_function(function_name) is None:
            if function_name != "":
                self._functions.append(Function(function_modifiers, return_type, function_name, arguments, line_number + 1, file_name, description, is_funct))

    def add_var(self, var_modifiers, var_name, comment, line_number, file_name, description=""):
        if self.get_variable(var_name) is None:
            self._variables.append(Variable(var_modifiers, var_name, comment, line_number + 1, file_name, description))

    def get_function(self, name):
        for function in self._functions:
            if function.function_name().lower() == name.lower():
                return function
        return None

    def get_variable(self, name):
        for variable in self._variables:
            if variable.name().lower() == name.lower():
                return variable
        return None

    # ! NEW
    def add_class(self, class_name, parent_class, description, file_name):
        if self.get_class(class_name) is None:
            self._classes.append(ClassReference(class_name, parent_class, description, file_name))

    # old (class_name, class_path, description)

    # ! TODO: adept to class object
    # ! NEW changed:
    def get_class(self, name):
        for _class in self._classes:
            if _class.name().lower() == name.lower():
                return _class
        return None

    # saves all completions to a file.
    # ! TODO: save per filename, save same functions multiple times, but add a variable if it already exists
    # ! NEW changed: don't save classes, filename at index 0
    def save_completions_to_file(self, filename):
        names = [x[0] for x in self._completions_for_file]

        if filename not in names:
            self._completions_for_file.append((filename, self._functions, self._variables))

    # returns the current suggestions for this file.
    def get_autocomplete_list(self, word, b_only_var=False, b_only_classes=False):
        autocomplete_list = []

        # filter relevant items:
        # ! TODO: adept to class object
        # ! NEW changed: done
        for _class in self._classes:
            if word.lower() in _class.name().lower():
                autocomplete_list.append((_class.name(), _class.name()))

        if not b_only_classes:
            for variable in self._variables:
                if word.lower() in variable.name().lower():
                    autocomplete_list.append((variable.name() + '\t' + variable.var_modifiers(), variable.name()))

            if not b_only_var:
                for function in self._functions:
                    if word.lower() in function.function_name().lower():
                        function_str = function.function_name() + '\t(' + function.arguments() + ')'    # add arguments
                        autocomplete_list.append((function_str, function.function_name()))

        return autocomplete_list


# Creates threads (FunctionsCollectorThread) for collecting any function, event or variable in the project folder that is relevant. e.g. collects from parent classes.
class FunctionsCollector(UnrealScriptAutocomplete, sublime_plugin.EventListener, HelperObject):
    # active threads
    _collector_threads = []
    # files that have already been parsed
    _filenames = []

    b_did_autocomplete = False

    # clear functions for current file
    # def on_close(self, view):
    #     pass

    # gets called when a file is saved. reset everything
    # ! TODO: only re-parse the just saved file
    def on_post_save(self, view):
        if view.file_name() is not None and is_unrealscript_file(view.file_name()):
            self.clear_all()
            # self.on_activated(view)

    # start parsing when a tab becomes active
    # ! TODO:   start parsing when sublime is opened.
    #           at startup, scan for all classes and save them to _classes
    def on_activated(self, view):
        self.clear()    # empty the completions list, so that we only get the relevant ones.

        if view.file_name() is not None and is_unrealscript_file(view.file_name()):
            open_folder_arr = view.window().folders()   # Gets all opened folders in the Sublime Text editor.

            if view.file_name() not in self._filenames:     # if the file wasn't parsed before
                self._filenames.append(view.file_name())
                self.add_thread(view.file_name(), open_folder_arr)  # create a new thread to search for relevant functions for the active file

            else:
                # print("already parsed")
                # ! TODO:   load from all parent classes
                #           create a function for it
                # ! NEW changed: removed _classes, index change
                names = [x[0] for x in self._completions_for_file]
                for i, name in enumerate(names):
                    if view.file_name() == name:    # get the functions we saved for the current file
                        self._functions = self._completions_for_file[i][1]
                        self._variables = self._completions_for_file[i][2]
                        global functions_reference, variables_reference     # , classes_reference
                        functions_reference = self._functions
                        variables_reference = self._variables
                        # classes_reference = self._classes

            self.handle_threads(self._collector_threads, view)  # display progress bar

    # This function is called when auto-complete pop-up box is displayed.
    # Used to get context sensitive suggestions
    def on_query_completions(self, view, prefix, locations):
        current_file = view.file_name()
        completions = []
        b_got_list = False

        if current_file is not None and is_unrealscript_file(current_file):
            # check if in at class declaration:
            line = view.line(view.sel()[0])
            line_contents = view.substr(line)
            if "class" in line_contents and "extends" in line_contents:
                print "get classes"
                completions = self.get_autocomplete_list(prefix, False, True)
                b_got_list = True

            if not b_got_list:
                # if is in defaultproperties, only get variables:
                line_number = 1000000
                defaultproperties_region = view.find('defaultproperties', 0, sublime.IGNORECASE)
                if defaultproperties_region:
                    (line_number, col) = view.rowcol(defaultproperties_region.a)
                    (row, col) = view.rowcol(view.sel()[0].begin())
                    if row > line_number:
                        # below defaultproperties
                        completions = self.get_autocomplete_list(prefix, True)
                    else:
                        # above defaultproperties
                        completions = self.get_autocomplete_list(prefix)
                else:
                    # no defaultproperties found
                    completions = self.get_autocomplete_list(prefix)

        return (completions, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    # called right before auto completion.
    def on_query_context(self, view, key, operator, operand, match_all):
        current_file = view.file_name()
        if current_file is not None and is_unrealscript_file(current_file):
            if key == "insert_dynamic_snippet":
                region = view.sel()[0]
                if region.empty():
                    self.b_did_autocomplete = True

    # remove auto completion and insert dynamic snippet instead, just after auto completion
    # ! TODO:   fix problems with snippets in snippets.
    #           only remove completion if a better suggestion was found.
    def on_modified(self, view):
        current_file = view.file_name()

        if current_file is not None and is_unrealscript_file(current_file):
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

    # animates an activity bar.
    # does things when everything is finished
    def handle_threads(self, threads, view, i=0, dir=1):
        # remove finished threads
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
            view.set_status('UnrealScriptAutocomplete', 'UnrealScriptAutocomplete is Parsing [%s=%s]' % (' ' * before, ' ' * after))

            sublime.set_timeout(lambda: self.handle_threads(threads, view, i, dir), 100)
            return
        else:
            # ! TODO: somehow save this when a single thread is finished, not when all are done, probably do this in the thread itself..
            #finished and keep functions for later use
            self.save_completions_to_file(view.file_name())
            view.erase_status('UnrealScriptAutocomplete')
            # ! TODO: this should be done differently
            global functions_reference, variables_reference  # , classes_reference
            functions_reference = self._functions
            variables_reference = self._variables
            # classes_reference = self._classes

    # reset all and start from anew
    def clear_all(self):
        self.clear()
        self._completions_for_file = []
        self._filenames = []
        # re-parse (problem: no view object)
        # self.on_activated(view)


# create a new thread for scanning one file, as this may take a while.
# parses one file and creates a new thread for the parent class
class FunctionsCollectorThread(threading.Thread):
    def __init__(self, collector, filename, timeout_seconds, open_folder_arr):
        self.collector = collector
        self.timeout = timeout_seconds
        self.filename = filename
        self.open_folder_arr = open_folder_arr
        threading.Thread.__init__(self)

    def run(self):  # gets called when the thread is created
        if self.filename is not None:
            self.save_functions(self.filename)  # parse current file

            description = ""
            with open(self.filename, 'rU') as file_lines:
                for line in file_lines:
                    description += line
                    classline = re.match(r'(class\b.+\bextends )(\b.+\b)', line.lower())  # get class declaration line of current file
                    if classline is not None:
                        parent_class_name = classline.group(2)    # get parent class

                        # search open folders for parent class file
                        # ! TODO: use the _classes to search for the file and don't append classes here
                        for folder in self.open_folder_arr:
                            parent_file = self.search_file(folder, parent_class_name)
                            # self.collector._classes.append((parent_class_name, parent_file, description))
                            if parent_file is not None:
                                self.collector.add_thread(parent_file, self.open_folder_arr)    # create a new thread to do the same stuff on the parent_file
                                break
                            else:
                                pass    # print "parent file not found in: ", folder
                        break

        # ! TODO: here i should probably save all found completions to the _completions_for_file
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
                if match is not None:
                    return match

    # extract functions, event and variables (TODO: STRUCTS, ENUMS, CONST) and split them into smaller groups.
    def save_functions(self, file_name):
        with open(file_name, 'rU') as file_lines:
            current_documentation = ""
            long_line = ""
            b_function = True
            bBracesNotOnSameLine = False
            for i, line in enumerate(file_lines):
                if line == "":
                    continue
                if "/**" in line:                       # start capturing documentation
                    current_documentation = line
                elif line.lstrip() != "" and "/" == line.lstrip()[0] and current_documentation == "":
                    current_documentation = line

                if line.lstrip() != "" and (line.lstrip()[0] == '*' or line.lstrip()[0] == '/'):  # add to documentation
                    if current_documentation != line:
                        current_documentation += line
                    continue

                if bBracesNotOnSameLine:
                    if ')' in line:
                        bBracesNotOnSameLine = False
                        new_line = ' '.join(long_line.split())
                        function_matches = self.extract_complicated_function(new_line, b_function)
                        self.collector.add_func(function_matches[0], function_matches[1], function_matches[2], function_matches[3], i, file_name, current_documentation, b_function)
                        current_documentation = ""
                        continue
                    else:
                        long_line += line

                if "function" in line.lower() or "event" in line.lower():  # get possible lines containing functions / events
                    if "function" in line.lower():
                        b_function = True
                        regex_str = r'(.*)\bfunction \b(\b.*\b)(.+)\((.*)\)'
                    elif "event" in line.lower():
                        b_function = False
                        regex_str = r'(.*)\bevent \b(\b.*\b)(.+)\((.*)\)'

                    matches = re.search(regex_str, line)        # search for:  1: modifiers, 2: return type, 3: name, 4: arguments
                    if matches is not None:
                        if matches.group(3) is None or matches.group(3) == " ":     # fail
                            matches = self.extract_complicated_function(line, b_function)   # try again without regex
                            self.collector.add_func(matches[0], matches[1], matches[2], matches[3], i, file_name, current_documentation, b_function)
                            current_documentation = ""
                            continue
                        else:
                            self.collector.add_func(matches.group(1), matches.group(2), matches.group(3), matches.group(4), i, file_name, current_documentation, b_function)
                            current_documentation = ""
                            continue

                    else:   # epic fail of my regex, try with python:
                        if b_function:
                            if 'function' not in line.split('//')[0]:   # the keyword was in the comments
                                continue
                        else:
                            if 'event' not in line.split('//')[0]:
                                continue

                        new_line = ' '.join(line.split())
                        matches = re.search(regex_str, new_line)        # search for:  1: modifiers, 2: return type, 3: name, 4: arguments
                        if matches is not None:
                            if matches.group(3) is None or matches.group(3) == " ":
                                matches = self.extract_complicated_function(new_line, b_function)
                                self.collector.add_func(matches[0], matches[1], matches[2], matches[3], i, file_name, current_documentation, b_function)
                                current_documentation = ""
                                continue
                            else:
                                self.collector.add_func(matches.group(1), matches.group(2), matches.group(3), matches.group(4), i, file_name, current_documentation, b_function)
                                current_documentation = ""
                                continue
                        else:
                            bBracesNotOnSameLine = True
                            long_line = new_line

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

    # manual extraction, because I failed at regex :(
    def extract_complicated_function(self, line, b_function):
        matches = []
        if b_function:
            function_split = line.split('function')
        else:
            function_split = line.split('event')
        if len(function_split) > 1:
            braces_split = function_split[1].split('(')
        else:
            return ["", "", "", ""]

        matches.append(function_split[0])  # function modifiers
        if len(braces_split[0].split()) > 1:   # if name and return:
            matches.append(braces_split[0].split()[0])     # return
            matches.append(braces_split[0].split()[1])     # name
        else:
            matches.append('')     # no return
            matches.append(braces_split[0])    # name
        if len(braces_split) > 1:
            matches.append(braces_split[1].rstrip('\n\r\t ;)'))    # parameters
        else:
            return ["", "", "", ""]

        return matches

    def stop(self):
        if self.isAlive():
            self._Thread__stop()


def is_unrealscript_file(filename):
    return '.uc' in filename


def is_unreal_log_file(filename):
    return '.log' in filename


# class to store a function/ event
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
                            {"contents": (Function_Snippet_Declaration % {  "function_modifiers": self._function_modifiers,
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


# ! NEW stores classes
class ClassReference:
    def __init__(self, class_name, parent_class, description, file_name):
        self._name = class_name
        self._description = description
        self._file_name = file_name
        self._parent_class = parent_class

    def description(self):
        return self._description

    def name(self):
        return self._name

    def file_name(self):
        return self._file_name

    def parent_class(self):
        return self._parent_class

    def insert_dynamic_snippet(self, view):
        self.create_dynamic_tooltip(view)
        view.run_command("insert_snippet", {"contents": (Class_Variable % {"name": self._name})})

    def create_dynamic_tooltip(self, view):
        documentation = self.description() + "class " + self.name() + "extends " + self.parent_class() + ";"
        print_to_panel(view, documentation)


Function_Snippet_Declaration = \
"""%(description)s%(function_modifiers)s%(return_type)s%(funct)s %(function_name)s(%(arguments)s)
{
    ${2:super.%(function_name)s(%(less_arguments)s);}
    ${3://}
}
"""

Function_Snippet_Call = \
"""%(function_name)s(%(arguments)s)%(end_stop)s"""

Variable_Snippet_Declaration = \
"""%(description)s%(var_modifiers)s%(name)s;%(comment)s
"""

Variable_Snippet_Name = \
"""%(name)s"""

Class_Variable = \
"""%(name)s"""
