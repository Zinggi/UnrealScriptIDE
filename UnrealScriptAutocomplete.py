#-----------------------------------------------------------------------------------
# UnrealScriptIDE Auto-complete Plug-in
#-----------------------------------------------------------------------------------
#	This plug-in displays classes, variables and Functions with parameters.
#   It searches in all parent classes of the current class.
#   Uses context sensitive completions.
#
# ! TODO:
#       -load auto complete suggestions from current object before a '.'
#       -same for goto definition (almost there...)
#
# ! BUGS:
#       -freeze at start-up because I'm parsing all classes
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

b_wanted_to_go_to_definition = False


# if the helper panel is displayed, this is true
b_helper_panel_on = False


# prints the text to the "helper panel" (Actually the console)
def print_to_panel(view, text):
    global b_helper_panel_on
    panel = view.window().get_output_panel('UnrealScriptAutocomplete_panel')
    panel_edit = panel.begin_edit()
    panel.insert(panel_edit, panel.size(), text)
    panel.end_edit(panel_edit)
    panel.show(panel.size())
    view.window().run_command("show_panel", {"panel": "output.UnrealScriptAutocomplete_panel"})
    b_helper_panel_on = True


def is_unrealscript_file():
    window = sublime.active_window()
    if window is None:
        return False
    view = window.active_view()
    if view is None:
        return False
    return "UnrealScript" in view.settings().get('syntax')


# ! TODO: write similar to is_unrealscript_file
def is_unreal_log_file(filename):
    return '.log' in filename


####################################################
# Go to Declaration
# -----------------
#
# ! TODO:
#   - object orientated
#   - erase status 'not found'
#   - change is_unreal_log_file
####################################################

# opens the definition of the current selected word.
#  - if b_new_start_point is true, the current cursor position will be stored.
class UnrealGotoDefinitionCommand(sublime_plugin.TextCommand):
    def run(self, edit, b_new_start_point=False):
        active_file = self.view.file_name()

        if is_unrealscript_file():  # old: and active_file is not None and
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

            # ! TODO:   object.*
            # analyzes what happens on this line
            skip_number = 0
            line = self.view.substr(self.view.line(self.view.sel()[0]))
            left_line = line.rsplit(word, 1)[0].lstrip().lower()

            # something with a '.'
            if left_line != "" and left_line[-1] == '.':
                if left_line[-6:-1] == "super":
                    # go to the super declaration
                    skip_number = 1

                # something like 'super(blabla).' or 'Actor(controller).'
                if left_line[-2:-1] == ").":
                    if "super(" in left_line:
                        print "super(something). is not supported yet!!!!"
                    else:
                        print "typecasting is not supported yet!!!"

                else:
                    # get object before the dot
                    obj = left_line[:-1].split()[-1]
                    var = self.get_variable(obj)
                    if var is not None:
                        o = self.search_in_class(word, var.var_modifiers().split()[-1])
                        if o is not None:
                            self.open_file(o.file_name(), o.line_number(), b_new_start_point)
                            return

            # no '.' (probably a declaration)
            elif left_line != "" and ("function" in left_line or "event" in left_line):
                skip_number = 1

            # search the current word in functions, variables and classes and if found, open the file.
            _class = self.get_class(word)
            if _class is not None:
                self.open_file(_class.file_name(), 1, b_new_start_point)
                return

            function = self.get_function(word, skip_number)
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

    # returns the function with this name. if skip_number is set it will skip to the super. declaration
    def get_function(self, name, skip_number=0):
        global functions_reference
        skiped_function = None
        for function in functions_reference:
            if function.function_name().lower() == name.lower():
                if skip_number == 0:
                    return function
                else:
                    skip_number -= 1
                    skiped_function = function
        return skiped_function

    def get_variable(self, name):
        global variables_reference
        for variable in variables_reference:
            if variable.name().lower() == name.lower():
                return variable
        return None

    # returns the class with the given name
    def get_class(self, name):
        global classes_reference
        for _class in classes_reference:
            if _class.name().lower() == name.lower():
                return _class
        return None

    # search the given word in the functions and variables of the given class_name.
    # returns the found object. If the class wasn't parsed before, this will parse the class.
    def search_in_class(self, word, class_name):
        c = self.get_class(class_name)
        if c is not None:
            f = c.get_function(word)
            if f is not None:
                return f
            v = c.get_variable(word)
            if v is not None:
                return v
            c.parse_me(self.view)
            global b_wanted_to_go_to_definition
            # so when parsing is finished we can try it again
            b_wanted_to_go_to_definition = True
        return None

####################################################
# Auto Completion and Parsing
# ---------------------------
#
# ! TODO:
#   -
####################################################


# base class for adding new auto-complete suggestions
class UnrealScriptAutocomplete:
    # store all classes (not just parent classes)
    # At the beginning search trough the whole source folder and fill this
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
    # store all variables
    _variables = []

    # clear the completions for the current file. To reset, use clear_all
    def clear(self):
        self._functions = []
        self._variables = []

    # returns the found function in _functions
    def get_function(self, name):
        for function in self._functions:
            if function.function_name().lower() == name.lower():
                return function
        return None

    # returns the found variable in _variables
    def get_variable(self, name):
        for variable in self._variables:
            if variable.name().lower() == name.lower():
                return variable
        return None

    # adds the class to _classes
    def add_class(self, class_name, parent_class, description, file_name):
        if self.get_class(class_name) is None:
            self._classes.append(ClassReference(class_name, parent_class, description, file_name, self))

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

    # returns all completions for a class and all its parent classes.
    # ATTENTION! takes a filename as an argument, not a class name
    def get_completions_from_class(self, class_file_name):
        my_class = self.get_class_from_filename(class_file_name)
        completions = (self.get_functions_from_class(my_class), self.get_variables_from_class(my_class))
        return completions

    # returns all functions from the given class and all its parent classes
    def get_functions_from_class(self, my_class):
        functions = []
        functions += my_class.get_functions()

        parent_file = self.get_class(my_class.parent_class())
        if parent_file is None:
            return functions

        functions += self.get_functions_from_class(parent_file)
        return functions

    # returns all variables from the given class and all its parent classes
    def get_variables_from_class(self, my_class):
        variables = []
        variables += my_class.get_variables()

        parent_file = self.get_class(my_class.parent_class())
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
                global functions_reference, variables_reference
                functions_reference = self._functions
                variables_reference = self._variables
                break

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
    # ! TODO: Maybe get completions directly from the _classes?
    def get_autocomplete_list(self, word, b_only_var=False, b_only_classes=False):
        autocomplete_list = []

        # filter relevant items:
        for _class in self._classes:
            if word.lower() in _class.name().lower():
                autocomplete_list.append((_class.name() + '\t' + "Class", _class.name()))

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


# Creates threads (FunctionsCollectorThread) for collecting any function, event or variable
# Handles all events
# Also, this is the main instance of my plug-in.
class FunctionsCollector(UnrealScriptAutocomplete, sublime_plugin.EventListener):
    # ! TODO: fix startup bug: is true at the very beginning, but setting it to true,
    # therefore parsing all classes, freezes sublime at startup
    b_first_time = True
    # when the first UnrealScript file is opened, all classes will be parsed.
    # During this time, no other threads shall be created and this will be True.
    b_still_parsing_classes = True

    # active threads
    _collector_threads = []

    # will be set to true just after auto-completion
    b_did_autocomplete = False

    # the line number at which the help panel was displayed last
    help_panel_line_number = -1

    # ! TODO: clear completions for current file
    # def on_close(self, view):
    #     pass

    # ! TODO: was a fix for the startup freeze. Might still work
    # def on_load(self, view):
    #     sublime.set_timeout(lambda: self.activate_plugin(), 1000)
    # def activate_plugin(self):
    #     self.b_first_time = True

    # gets called when a file is saved. re-parse the current file.
    def on_post_save(self, view):
        if is_unrealscript_file():
            filename = view.file_name()
            if filename is not None:
                self.remove_file(filename)
                self.on_activated(view)

    # start parsing the active file when a tab becomes active
    # at startup, scan for all classes and save them to _classes
    def on_activated(self, view):
        self.clear()    # empty the completions list, so that we only get the relevant ones.

        if is_unrealscript_file():
            # at startup, save all classes
            if self.b_first_time:
                print "startup: start parsing classes..."
                open_folder_arr = view.window().folders()   # Gets all opened folders in the Sublime Text editor.
                self._collector_threads.append(ClassesCollectorThread(self, "", 30, open_folder_arr, True))
                self._collector_threads[-1].start()
                self.b_first_time = False
                self.handle_threads(self._collector_threads, view)  # display progress bar
                return

            # wait for the classes threads to be completed, then parse the current file.
            if not self.b_still_parsing_classes and view.file_name() is not None:
                # if the file wasn't parsed before, parse it now.
                if view.file_name() not in self._filenames:
                    print "start parsing file: ", view.file_name()
                    self._filenames.append(view.file_name())
                    self.add_function_collector_thread(view.file_name())  # create a new thread to search for relevant functions for the active file
                    self.handle_threads(self._collector_threads, view)  # display progress bar

                else:
                    print "already parsed, load completions for file: ", view.file_name()
                    self.load_completions_for_file(view.file_name())

    # This function is called when auto-complete pop-up box is displayed.
    # Used to get context sensitive suggestions
    def on_query_completions(self, view, prefix, locations):
        completions = []
        b_got_list = False

        if is_unrealscript_file():
            # check if on a class declaration line:
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

            return completions  # , sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    # called right before auto completion.
    def on_query_context(self, view, key, operator, operand, match_all):
        if is_unrealscript_file():
            if key == "insert_dynamic_snippet":
                region = view.sel()[0]
                if region.empty():
                    self.b_did_autocomplete = True

    # remove auto completion and insert dynamic snippet instead, just after auto completion
    def on_modified(self, view):
        if is_unrealscript_file():
            # if the helper panel is displayed, save the line number
            global b_helper_panel_on
            if b_helper_panel_on:
                self.help_panel_line_number = view.rowcol(view.sel()[0].begin())[0]
                b_helper_panel_on = False

            if self.help_panel_line_number != -1:
                # if we are modifying anything above or below the helper panel line, hide the panel.
                if view.rowcol(view.sel()[0].begin())[0] != self.help_panel_line_number:
                    view.window().run_command("hide_panel", {"panel": "output.UnrealScriptAutocomplete_panel"})
                    self.help_panel_line_number = -1

            if self.b_did_autocomplete:
                self.b_did_autocomplete = False

                sublime.set_timeout(lambda: self.insert_dynamic_snippet_for_completion(view), 0)

    # if there is a dynamic snippet available for the just added word, remove the last word and insert the snippet instead
    def insert_dynamic_snippet_for_completion(self, view):
        region_word = view.word(view.sel()[0])
        word = view.substr(region_word)

        if not all(c.isspace() for c in word):  # only if the current word doesn't contain any whitespace character
            f = self.get_function(word)
            v = self.get_variable(word)
            c = self.get_class(word)
            if c or f or v:
                edit = view.begin_edit('UnrealScriptAutocomplete')
                view.replace(edit, region_word, "")     # remove last word
                view.end_edit(edit)
                if c:
                    c.insert_dynamic_snippet(view)      # insert class snippet instead
                elif f:
                    f.insert_dynamic_snippet(view)      # insert function snippet instead
                elif v:
                    v.insert_dynamic_snippet(view)      # insert function snippet instead

    # creates a thread to parse the given file_name and all its parent classes
    def add_function_collector_thread(self, file_name):
        self._collector_threads.append(FunctionsCollectorThread(self, file_name, 30))
        self._collector_threads[-1].start()

    # animates an activity bar.
    # serves as an event for when all threads are done
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
            view.erase_status('UnrealScriptAutocomplete')
            if self.b_still_parsing_classes:
                print "finished parsing classes, start parsing current file"
                self.b_still_parsing_classes = False
                global classes_reference
                classes_reference = self._classes
                self.on_activated(view)
            else:
                global b_wanted_to_go_to_definition
                if b_wanted_to_go_to_definition:
                    b_wanted_to_go_to_definition = False
                    view.run_command("unreal_goto_definition")
                else:
                    print "finished parsing file: ", view.file_name()
                    #finished and keep functions for later use
                    self._functions, self._variables = self.get_completions_from_class(view.file_name())
                    self.save_completions_to_file(view.file_name())
                    view.erase_status('UnrealScriptAutocomplete')
                    # ! TODO: this should be done differently
                    global functions_reference, variables_reference
                    functions_reference = self._functions
                    variables_reference = self._variables

    # reset all and start from anew
    # I don't think that's used anymore...
    def clear_all(self):
        self.b_first_time = True
        self.clear()
        self._completions_for_file = []
        self._filenames = []
        for c in self._classes:
            c.clear()
        # ! BUG: re-parse (problem: no view object)
        # self.on_activated(view)


# Adds the class inside (filename) to the collector.
# if b_first is true, creates a thread for every file in the src directory
class ClassesCollectorThread(threading.Thread):
    def __init__(self, collector, filename, timeout_seconds, open_folder_arr, b_first=False):
        self.collector = collector
        self.timeout = timeout_seconds
        self.filename = filename
        self.open_folder_arr = open_folder_arr
        self.b_first = b_first
        threading.Thread.__init__(self)

    def run(self):  # gets called when the thread is created
        if self.b_first:
            for f in self.open_folder_arr:
                if "Development\\Src" in f:
                    self.get_classes(f, self.open_folder_arr)
            self.stop()

        else:
            if self.filename is not None:
                self.save_classes()
                self.stop()

    # creates a new thread for every file in the src directory
    def get_classes(self, path, open_folder_arr):
        for file in os.listdir(path):
            dirfile = os.path.join(path, file)
            if os.path.isfile(dirfile):
                fileName, fileExtension = os.path.splitext(dirfile)

                if fileExtension == ".uc":
                    self.collector._collector_threads.append(ClassesCollectorThread(self.collector, dirfile, 30, open_folder_arr))
                    self.collector._collector_threads[-1].start()

            elif os.path.isdir(dirfile):
                self.get_classes(dirfile, open_folder_arr)

    # parses the filename and saves the class declaration to the _classes
    def save_classes(self):
        description = ""
        with open(self.filename, 'rU') as file_lines:
            for line in file_lines:
                description += line
                classline = re.match(r'(class\b.+\bextends )(\b.+\b)', line.lower())  # get class declaration line of current file
                if classline is not None:
                    parent_class_name = classline.group(2)  # get parent class
                    self.collector.add_class(os.path.basename(self.filename).split('.')[0],
                                             parent_class_name,
                                             description,
                                             self.filename)
                    break
                elif "class object" in line.lower():
                    self.collector.add_class(os.path.basename(self.filename).split('.')[0],
                                             "",
                                             description,
                                             self.filename)
                    break

    def stop(self):
        if self.isAlive():
            self._Thread__stop()


# parses one file and creates a new thread for the parent class
# this saves all functions and variables in the according classes object
# ! TODO: instead of the filename I could pass the class object
class FunctionsCollectorThread(threading.Thread):
    # stores all functions and information about them
    _functions = []
    # store all variables
    _variables = []

    def __init__(self, collector, filename, timeout_seconds):
        self.collector = collector
        self.timeout = timeout_seconds
        self.filename = filename
        self._functions = []
        self._variables = []
        threading.Thread.__init__(self)

    def run(self):  # gets called when the thread is created
        if self.filename is not None:
            # get_file_name is used here to check if this file was already parsed
            my_class = self.collector.get_class_from_filename(self.filename)
            if my_class is not None and my_class.get_functions() != []:
                print "already parsed: ", self.filename
                self.stop()
                return

            self.save_functions(self.filename)  # parse current file

            parent_class_name = my_class.parent_class()
            parent_file = self.get_file_name(parent_class_name)
            if parent_file is not None:
                self.collector.add_function_collector_thread(parent_file)   # create a new thread to parse the parent_file too

            my_class.save_completions(self._functions, self._variables)

        self.stop()

    # adds the function to _functions
    def add_func(self, function_modifiers, return_type, function_name, arguments, line_number, file_name, description="", is_funct=1):
        if self.get_function(function_name) is None:
            if function_name != "":
                self._functions.append(Function(function_modifiers, return_type, function_name, arguments, line_number + 1, file_name, description, is_funct))

    # adds the variable to _variables
    def add_var(self, var_modifiers, var_name, comment, line_number, file_name, description=""):
        if self.get_variable(var_name) is None:
            self._variables.append(Variable(var_modifiers, var_name, comment, line_number + 1, file_name, description))

    # returns the found function
    def get_function(self, name):
        for function in self._functions:
            if function.function_name().lower() == name.lower():
                return function
        return None

    # returns the found variable
    def get_variable(self, name):
        for variable in self._variables:
            if variable.name().lower() == name.lower():
                return variable
        return None

    # returns the filename of the given class name
    def get_file_name(self, class_name):
        parent_class = self.collector.get_class(class_name)
        if parent_class is not None:
            return parent_class.file_name()
        return None

    # extract functions, event and variables and split them into smaller groups.
    # ! TODO:   -support STRUCTS, ENUMS, CONST
    #           -Probably rewrite this, as it is pretty ugly
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
                        self.add_func(function_matches[0], function_matches[1], function_matches[2], function_matches[3], i, file_name, current_documentation, b_function)
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
                            self.add_func(matches[0], matches[1], matches[2], matches[3], i, file_name, current_documentation, b_function)
                            current_documentation = ""
                            continue
                        else:
                            self.add_func(matches.group(1), matches.group(2), matches.group(3), matches.group(4), i, file_name, current_documentation, b_function)
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
                                self.add_func(matches[0], matches[1], matches[2], matches[3], i, file_name, current_documentation, b_function)
                                current_documentation = ""
                                continue
                            else:
                                self.add_func(matches.group(1), matches.group(2), matches.group(3), matches.group(4), i, file_name, current_documentation, b_function)
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
                        self.add_var(var_line, name, doc_line, i, file_name, current_documentation)
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


# -------------------------------------
# Classes, Functions and Variables
# -----------------
#
# These can create dynamic tool-tips and dynamic snippets based on their content
# ___________________________________

# stores classes
# every class can also store all functions and variables that are inside this class
class ClassReference:
    _functions = []
    _variables = []

    def __init__(self, class_name, parent_class, description, file_name, collector_reference):
        self._name = class_name
        self._description = description
        self._file_name = file_name
        self._parent_class = parent_class
        self._collector_reference = collector_reference

    def description(self):
        return self._description

    def name(self):
        return self._name

    def file_name(self):
        return self._file_name

    def parent_class(self):
        return self._parent_class

    def save_completions(self, functions, variables):
        self._variables = variables
        self._functions = functions

    def clear(self):
        self._functions = []
        self._variables = []

    # returns all _functions that were stored inside this class. If this returns [], it wasn't parsed already
    def get_functions(self):
        return self._functions

    def get_function(self, name):
        for f in self._functions:
            if name.lower() == f.function_name().lower():
                return f
        p_class = self._collector_reference.get_class(self._parent_class)
        if p_class is not None:
            return p_class.get_function(name)
        return None

    def get_variable(self, name):
        for v in self._variables:
            if name.lower() == v.name().lower():
                return v
        p_class = self._collector_reference.get_class(self._parent_class)
        if p_class is not None:
            return p_class.get_variable(name)
        return None

    def get_variables(self):
        return self._variables

    def parse_me(self, view):
        self._collector_reference.add_function_collector_thread(self._file_name)  # create a new thread to search for relevant functions for this class
        self._collector_reference.handle_threads(self._collector_reference._collector_threads, view)  # display progress bar

    def insert_dynamic_snippet(self, view):
        self.create_dynamic_tooltip(view)
        view.run_command("insert_snippet", {"contents": (Class_Variable % {"name": self._name})})

    def create_dynamic_tooltip(self, view):
        documentation = self.description()
        print_to_panel(view, documentation)


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


# --------------------------------
# Dynamic Snippets
# ----------------

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


########################################################
#Event
#-----
# this one is taken from: http://www.valuedlessons.com/2008/04/events-in-python.html
# I should probably use events instead of some global variables
########################################################
# class Event:
#     def __init__(self):
#         self.handlers = set()

#     def handle(self, handler):
#         self.handlers.add(handler)
#         return self

#     def unhandle(self, handler):
#         try:
#             self.handlers.remove(handler)
#         except:
#             raise ValueError("Handler is not handling this event, so cannot unhandle it.")
#         return self

#     def fire(self, *args, **kargs):
#         for handler in self.handlers:
#             handler(*args, **kargs)

#     def getHandlerCount(self):
#         return len(self.handlers)

#     __iadd__ = handle
#     __isub__ = unhandle
#     __call__ = fire
#     __len__  = getHandlerCount


# class MockFileWatcher:
#     def __init__(self):
#         self.fileChanged = Event()

#     def watchFiles(self):
#         source_path = "foo"
#         self.fileChanged(source_path)

# def log_file_change(source_path):
#     print "%r changed." % (source_path,)

# def log_file_change2(source_path):
#     print "%r changed!" % (source_path,)

# watcher              = MockFileWatcher()
# watcher.fileChanged += log_file_change2
# watcher.fileChanged += log_file_change
# watcher.fileChanged -= log_file_change2
# watcher.watchFiles()