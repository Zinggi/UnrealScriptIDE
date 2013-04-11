#-----------------------------------------------------------------------------------
# UnrealScriptIDE Auto-complete Plug-in
#-----------------------------------------------------------------------------------
#	This plug-in displays classes, variables and Functions with parameters.
#   It searches in all parent classes of the current class.
#   Uses context sensitive completions.
#
# ! TODO:
#       -use more events!
#       -re-parse classes if a new class is created or a class declaration changes.
#           problematic if this is done with another application or if a file is deleted.
#       -live parsing of current file.
#       -local variable support
#       -inbuilt functions
#
# (c) Florian Zinggeler
#-----------------------------------------------------------------------------------
import sublime
import sublime_plugin
import threading
import os
import re
import pickle


# get the event manager
def evt_m():
    return event_manager

event_manager = None

last_location = None
current_location = None

# if the helper panel is displayed, this is true
# ! (TODO): use an event instead
b_helper_panel_on = False


# prints the text to the "helper panel" (Actually the console)
# ! (TODO): fire show_helper_panel
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
    return "UnrealScriptIDE/UnrealScript.tmLanguage" in view.settings().get('syntax')


# ! TODO: write similar to is_unrealscript_file
def is_unreal_log_file(filename):
    return '.log' in filename


# returns the code fragment that is actually relevant for auto-completion / go to declaration.
# e.g. a single statement
#   something = other + function(a, b).foo. returns function().foo.
def get_relevant_text(text):
    left_line = text.lstrip().lower()
    i = 0
    obj_string = ""
    for c in left_line[::-1]:
        obj_string += c
        if c == ')':
            i += 1
        elif c == '(':
            i -= 1
        if (c == ' ' or c == ',' or c == '\t') and i == 0:
            return obj_string[-2::-1]
        elif c == '(' and i == -1:
            return obj_string[-2::-1]
    return obj_string[::-1].lstrip()


####################################################
# Go to Declaration
# -----------------
#
# ! (TODO):
#   - erase status 'not found'
####################################################

# opens the definition of the current selected word.
#  - if b_new_start_point is true, the current cursor position will be stored as a return point.
class UnrealGotoDefinitionCommand(sublime_plugin.TextCommand):
    def run(self, edit, b_new_start_point=False, line_number=-1, filename=""):
        if is_unrealscript_file():
            # open the file at line line_number if specified (gets called after it was calculated by the main instance)
            if line_number != -1 and filename != "":
                self.open_file(filename, line_number, b_new_start_point)
                return

            # get selected word
            region_word = self.view.word(self.view.sel()[0])
            word = self.view.substr(region_word)

            # if no word is selected or the cursor is at the beginning of the line, return to last location
            global last_location, current_location
            row, col = self.view.rowcol(self.view.sel()[0].begin())

            if last_location is not None and (word.strip() == "" or col == 0):
                active_file = self.view.file_name()

                if current_location.lower() == active_file.lower():
                    window = sublime.active_window()
                    window.open_file(last_location, sublime.ENCODED_POSITION)
                    window.open_file(last_location, sublime.ENCODED_POSITION)
                    last_location = None
                    return

            # get line left of cursor
            line = self.view.substr(sublime.Region(self.view.line(self.view.sel()[0]).begin(), region_word.begin()))
            line = line.lstrip().lower()
            # print line

            # if the end of the line is a whitespace or a '(' (meaning it is a function argument)
            # empty left_line
            if line == "" or ' ' == line[-1] or '\t' == line[-1] or '(' == line[-1]:
                left_line = ""
            else:
                # get relevant part of the line
                left_line = get_relevant_text(line)
                # print left_line

            # calculate where to go inside the main instance of my plug-in.
            # Then, call this command again with a filename and a line number.
            evt_m().go_to_definition(left_line, word, line, b_new_start_point)

        elif is_unreal_log_file(self.view.file_name()):
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


####################################################
# Auto Completion and Parsing
# ---------------------------
#
####################################################


# base class for adding new auto-complete suggestions
# takes care of building up the data structure and handling it.
class UnrealScriptAutocomplete:
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

    # clear the completions for the current file.
    def clear(self):
        self._functions = []
        self._variables = []

    # returns the found function in _functions
    def get_function(self, name):
        for function in self._functions:
            if isinstance(function, basestring):
                continue
            if function.function_name().lower() == name.lower():
                return function
        return None

    # returns the found variable in _variables
    def get_variable(self, name):
        for variable in self._variables:
            if isinstance(variable, basestring):
                continue
            if variable.name().lower() == name.lower():
                return variable
        return None

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

    # returns the found object inside out_of (self, class object)
    def get_object(self, word, out_of, b_no_classes=False, b_no_functions=False, b_no_variables=False, b_second_type=False):
        # print "get object '" + word + "'\tout of ", out_of
        # don't try to get classes out of a class
        if not out_of:
            out_of = self
        if word[-1:] == ']':
            word = word.split('[')[0]
        elif b_second_type:
            b_second_type = False
        if isinstance(out_of, Struct):
            return out_of.get_variable(word)
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

# ==============================
# Completions
# ==============================

    # returns the current suggestions for this file.
    # if from_class is given, returns the completions for the given class
    def get_autocomplete_list(self, word, b_no_classes=False, b_no_functions=False, b_no_variables=False, from_class=None, bNoStandardCompletions=False):
        unsorted_autocomplete_list = []
        current_list = -1
        autocomplete_list = []

        if from_class:
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

        # filter relevant items:
        if not b_no_variables:
            for variable in variables:
                if isinstance(variable, basestring):
                    current_list += 1
                    unsorted_autocomplete_list.append([(variable, "")])
                elif word.lower() in variable.name().lower():
                    unsorted_autocomplete_list[current_list].append((variable.name() + '\t' + variable.var_modifiers(), variable.name()))
                    # autocomplete_list.append((variable.name() + '\t' + variable.var_modifiers(), variable.name()))

        if not b_no_functions:
            for function in functions:
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
            return ([], class_file_name.get_variables())
        if isinstance(class_file_name, ClassReference):
            my_class = class_file_name
        else:
            my_class = self.get_class_from_filename(class_file_name)
        if my_class.has_parsed():
            return (self.get_functions_from_class(my_class), self.get_variables_from_class(my_class))
        else:
            my_class.parse_me()
            return ("parsing...", "parsing...")

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


# Creates threads (FunctionsCollectorThread) for collecting any function, event or variable
# Handles all events
# Also, this is the main instance of my plug-in.
class FunctionsCollector(UnrealScriptAutocomplete, sublime_plugin.EventListener):
    # at startup, this is true
    b_first_time = True
    # when the first UnrealScript file is opened, all classes will be parsed.
    # During this time, no other threads shall be created and this will be True.
    b_still_parsing_classes = True

    # active threads
    _collector_threads = []

    # the path to the src folder. This is used to save and load the cache files.
    src_folder = ""

    # will be set to true just after auto-completion
    b_did_autocomplete = False
    # if it needs to parse first, this will be true
    b_wanted_to_autocomplete = False
    # the class we wanted to load completions from
    completion_class = None

    # if it needs to parse before go to definition, this is true.
    b_wanted_to_go_to_definition = False

    # the line number at which the help panel was displayed last
    help_panel_line_number = -1

    b_rebuild_cache = False

    # ! (TODO): clear completions for current file
    # def on_close(self, view):
    #     pass

    # gets called when a file is saved. re-parse the current file.
    def on_post_save(self, view):
        if is_unrealscript_file():
            filename = view.file_name()
            if filename is not None:
                self.remove_file(filename)
                self.on_activated(view)

    # start parsing the active file when a tab becomes active
    # at first startup, scan for all classes and save them to _classes
    # at later startups, load _classes from cache.
    def on_activated(self, view):
        if is_unrealscript_file():
            self.clear()    # empty the completions list, so that we only get the relevant ones.
            # load breakpoints
            if view.window():
                view.window().run_command("unreal_load_breakpoints")

            # at startup, save all classes
            if self.b_first_time:
                self.b_first_time = False
                # register events
                global event_manager
                event_manager = EventManager()
                evt_m().go_to_definition += self.on_go_to_definition
                evt_m().rebuild_cache += self.on_rebuild_cache

                view.set_status('UnrealScriptAutocomplete', "startup: start parsing classes...")
                print "startup: start parsing classes..."
                open_folder_arr = view.window().folders()   # Gets all opened folders in the Sublime Text editor.
                self._collector_threads.append(ClassesCollectorThread(self, "", 30, open_folder_arr, True))
                self._collector_threads[-1].start()
                self.handle_threads(self._collector_threads, view)  # display progress bar
                return

            file_name = view.file_name()
            # wait for the classes threads to be completed, then parse the current file.
            if not self.b_still_parsing_classes and file_name is not None:
                # if the file wasn't parsed before, parse it now.
                if file_name not in self._filenames:
                    print "start parsing file: ", file_name
                    self._filenames.append(file_name)
                    self.add_function_collector_thread(file_name)  # create a new thread to search for relevant functions for the active file
                    self.handle_threads(self._collector_threads, view)  # display progress bar

                else:
                    print "already parsed, load completions for file: ", file_name
                    self.load_completions_for_file(file_name)

    # This function is called when auto-complete pop-up box is displayed.
    # Used to get context sensitive suggestions
    def on_query_completions(self, view, prefix, locations):
        if is_unrealscript_file():
            selection_region = view.sel()[0]
            line = view.line(selection_region)
            left_line_region = sublime.Region(line.begin(), selection_region.end())
            line_contents = view.substr(left_line_region)

            # if on a class declaration line, only get classes:
            if "class" in line_contents and "extends" in line_contents:
                return self.get_autocomplete_list(prefix, False, True, True, bNoStandardCompletions=True)

            # if is in defaultproperties, only get variables:
            line_number = 1000000
            defaultproperties_region = view.find('defaultproperties', 0, sublime.IGNORECASE)
            if defaultproperties_region:
                (line_number, col) = view.rowcol(defaultproperties_region.a)
                (row, col) = view.rowcol(selection_region.begin())
                if row > line_number:
                    # below defaultproperties
                    return self.get_autocomplete_list(prefix, True, True, bNoStandardCompletions=True)

            # no defaultproperties found or above defaults:

            # check if wants object oriented completions
            if len(line_contents) > 0 and line_contents[-1] == '.':    # I was probably thinking something here, but I don't remember: or ' ' not in line_contents.split('.')[-1]
                left_line = get_relevant_text(line_contents)
                if '.' != left_line[-1]:
                    left_line = ".".join(left_line.split('.')[:-1]) + '.'
                # print "object.* :  ", left_line

                c = self.get_class_from_context(left_line)
                if not c:
                    c = "type not found"
                if c != "parsing...":
                    return self.get_autocomplete_list(prefix, True, False, False, c, bNoStandardCompletions=True)
                else:
                    self.b_wanted_to_autocomplete = True
                    return [("just a moment...", "")]

            # get standard completions
            else:
                compl_default = [view.extract_completions(prefix)]
                compl_default = [(item + "\tbuffer", item) for sublist in compl_default for item in sublist]       # format
                keywords = [(item + "\tkeyword", item) for item in unreal_keywords]
                return self.get_autocomplete_list(prefix) + keywords + compl_default

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
            # if the helper panel has just been displayed, save the line number
            # ! (TODO): event instead of global
            global b_helper_panel_on
            if b_helper_panel_on:
                self.help_panel_line_number = view.rowcol(view.sel()[0].begin())[0]
                b_helper_panel_on = False

            elif self.help_panel_line_number != -1:
                # if we are modifying anything above or below the helper panel line, hide the panel.
                if view.rowcol(view.sel()[0].begin())[0] != self.help_panel_line_number:
                    view.window().run_command("hide_panel", {"panel": "output.UnrealScriptAutocomplete_panel"})
                    self.help_panel_line_number = -1

            if self.b_did_autocomplete:
                self.b_did_autocomplete = False
                # use timeout to reduce time needed inside the on_modified event
                sublime.set_timeout(lambda: self.insert_dynamic_snippet_for_completion(view, self.completion_class), 0)

    # if there is a dynamic snippet available for the just added word,
    # remove the last word and insert the snippet instead
    # if from_class is given, find the object inside this class
    def insert_dynamic_snippet_for_completion(self, view, from_class=None):
        region_word = view.word(view.sel()[0])
        word = view.substr(region_word)

        if not all(c.isspace() for c in word):  # only if the current word doesn't contain any whitespace character
            if from_class:
                o = self.get_object(word, from_class)
                self.completion_class = None
            else:
                o = self.get_object(word, self)

            if o is not None:
                edit = view.begin_edit('UnrealScriptAutocomplete')
                view.replace(edit, region_word, "")     # remove last word
                view.end_edit(edit)
                o.insert_dynamic_snippet(view)

    # go to the definition of the object below the cursor
    def on_go_to_definition(self, left_line, word, full_line, b_new_start_point):
        window = sublime.active_window()
        # print "on_go_to_definition: full_line:\t", full_line, "\t left_line:\t'" + left_line + "'\t Word:\t", word

        # probably a declaration or super.
        # => go to the parent declaration
        if "function" in full_line or "event" in full_line or left_line[-6:] == "super.":
            # try opening a class, if it fails, its a declaration (or super.)
            #                      if it doesn't, it's the return type
            if not self.get_and_open_object(word, self, window, b_new_start_point, False, True, True):
                # open parent declaration
                active_file = window.active_view().file_name()
                c = self.get_class_from_filename(active_file).get_parent()
                # c = self.get_class(self.get_class_from_filename(active_file).parent_class())
                self.get_and_open_object(word, c, window, b_new_start_point, True)

        # just a single object or self.
        elif left_line == "" or left_line[-5:] == "self.":
            if word == "super":
                # open parent class
                active_file = window.active_view().file_name()
                c = self.get_class_from_filename(active_file).parent_class()
                self.get_and_open_object(c, self, window, b_new_start_point)
            elif word == "self":
                # open the the declaration of the current file
                active_file = window.active_view().file_name()
                self.get_and_open_object(self.get_class_from_filename(active_file).name(), self, window, b_new_start_point)
            else:
                # open the declaration of the object
                self.get_and_open_object(word, self, window, b_new_start_point)

        # a dot before the object
        elif left_line != "" and left_line[-1] == '.':
            c = self.get_class_from_context(left_line)
            if c == "parsing...":
                window.active_view().set_status('UnrealScriptAutocomplete', "just a moment...")
                print "still parsing..."
                self.b_wanted_to_go_to_definition = True
                self.b_new_start_point = b_new_start_point
            else:
                self.get_and_open_object(word, c, window, b_new_start_point, True)
        else:
            print "case not handled!!!"

    # gets the object out of out_of and if found opens it
    # ! TODO: if there is a variable and a class, ask which to open.
    def get_and_open_object(self, word, out_of, window, b_new_start_point, b_no_classes=False, b_no_functions=False, b_no_variables=False):
        o = self.get_object(word, out_of, b_no_classes, b_no_functions, b_no_variables)
        # print "object ", o
        if o is not None and o != "parsing...":
            window.run_command("unreal_goto_definition", {"b_new_start_point": b_new_start_point, "line_number": o.line_number(), "filename": o.file_name()})
            return True
        elif o == "parsing...":
            window.active_view().set_status('UnrealScriptAutocomplete', "just a moment...")
            self.b_wanted_to_go_to_definition = True
            self.b_new_start_point = b_new_start_point
        else:
            window.active_view().set_status('UnrealScriptAutocomplete', word + " not found in current file and all parent classes!")
        return False

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
            self.save_classes_to_cache()
            view.erase_status('UnrealScriptAutocomplete')
            if self.b_still_parsing_classes:
                print "finished parsing classes, start parsing current file"
                self.b_still_parsing_classes = False
                # self.save_classes_to_cache()
                self.link_classes()
                self.on_activated(view)
            else:
                if self.b_wanted_to_go_to_definition:
                    print "wanted to go to definition!"
                    self.b_wanted_to_go_to_definition = False
                    sublime.active_window().run_command("unreal_goto_definition", {"b_new_start_point": self.b_new_start_point})
                elif self.b_wanted_to_autocomplete:
                    print "wanted to auto-complete!"
                    self.b_wanted_to_autocomplete = False
                    sublime.active_window().run_command("hide_auto_complete")
                    sublime.set_timeout(lambda: view.run_command("auto_complete"), 0)
                else:
                    # finished and keep functions for later use
                    self._functions, self._variables = self.get_completions_from_class(view.file_name())
                    self.save_completions_to_file(view.file_name())
                    view.erase_status('UnrealScriptAutocomplete')

    # reset all and start from anew
    def clear_all(self, view):
        self.b_first_time = True
        self.clear()
        self._completions_for_file = []
        self._filenames = []
        for c in self._classes:
            c.clear()
        self._classes = []
        self.b_rebuild_cache = True
        self.b_still_parsing_classes = True
        self.on_activated(view)

    # save the _classes array to a cache file in the src folder
    def save_classes_to_cache(self):
        if os.path.exists(self.src_folder):
            with open(os.path.join(self.src_folder, 'classes_cache.obj'), 'w') as cache_file:
                pickle.dump(self._classes, cache_file)

    # loads the _classes from the cache file
    def load_classes_from_cache(self):
        if os.path.exists(self.src_folder):
            with open(os.path.join(self.src_folder, 'classes_cache.obj'), 'r') as cache_file:
                self._classes = pickle.load(cache_file)
            for c in self._classes:
                c.set_collector_reference(self)

    def on_rebuild_cache(self, view):
        print "rebuild cache"
        self.clear_all(view)


# this deletes the cache file and clears every completion, so that it can then rebuild the classes.
# Resetting everything, basically starting from anew like it would be the first run.
class UnrealRebuildCacheCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if is_unrealscript_file():
            open_folder_arr = self.view.window().folders()
            if open_folder_arr:
                for f in open_folder_arr:
                    if "Development\\Src" in f:
                        # if we saved the classes to a cache before, delete it.
                        if os.path.exists(os.path.join(f, "classes_cache.obj")):
                            evt_m().rebuild_cache(self.view)
        else:
            print "no UnrealScript file, try again with a .uc file focused"


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
                    self.collector.src_folder = f
                    # if we saved the classes to a cache before, load them from there.
                    if not self.collector.b_rebuild_cache and os.path.exists(os.path.join(f, "classes_cache.obj")):
                        print "cache exists. Loading classes from memory"
                        self.collector.load_classes_from_cache()
                    else:
                        print "no cache file found, start parsing all classes"
                        self.get_classes(f, self.open_folder_arr)
                        self.get_inbuilt_classes(self.open_folder_arr)
                    break
            self.stop()

        else:
            if self.filename is not None:
                self.save_classes()
                self.stop()

    # creates a new thread for every file in the src directory
    def get_classes(self, path, open_folder_arr):
        for file in os.listdir(path):
            dirfile = os.path.join(path, file)
            if os.path.isfile(dirfile) and dirfile.endswith(".uc"):
                    self.collector._collector_threads.append(ClassesCollectorThread(self.collector, dirfile, 30, open_folder_arr))
                    self.collector._collector_threads[-1].start()

            elif os.path.isdir(dirfile):
                self.get_classes(dirfile, open_folder_arr)

    def get_inbuilt_classes(self, open_folder_arr):
        array = os.path.join(sublime.packages_path(), "UnrealScriptIDE\\Array.uc")
        class_class = os.path.join(sublime.packages_path(), "UnrealScriptIDE\\Class.uc")
        self.collector._collector_threads.append(ClassesCollectorThread(self.collector, array, 30, open_folder_arr))
        self.collector._collector_threads[-1].start()
        self.collector._collector_threads.append(ClassesCollectorThread(self.collector, class_class, 30, open_folder_arr))
        self.collector._collector_threads[-1].start()

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
                elif "class object" in line.lower() and "*" not in line[:3] and "/" not in line[:3]:
                    self.collector.add_class(os.path.basename(self.filename).split('.')[0],
                                             "",
                                             description,
                                             self.filename)
                    break
                elif "class array" in line.lower() and "*" not in line[:3] and "/" not in line[:3]:
                    self.collector.add_class(os.path.basename(self.filename).split('.')[0],
                                             "",
                                             description,
                                             self.filename)
                    break
                elif "class class" in line.lower() and "*" not in line[:3] and "/" not in line[:3]:
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
# ! (TODO): instead of the filename I could pass the class object
class FunctionsCollectorThread(threading.Thread):
    # stores all functions and information about them
    _functions = []
    # store all variables
    _variables = []
    # store all consts
    _consts = []
    _structs = []
    _struct_variables = []

    def __init__(self, collector, filename, timeout_seconds):
        self.collector = collector
        self.timeout = timeout_seconds
        self.filename = filename
        self._functions = []
        self._variables = []
        self._consts = []
        self._structs = []
        threading.Thread.__init__(self)

    def run(self):  # gets called when the thread is created
        if self.filename is not None:
            # check if this file was already parsed
            my_class = self.collector.get_class_from_filename(self.filename)
            if my_class is not None and my_class.has_parsed():
                print "already parsed: ", self.filename
                self.stop()
                return

            elif my_class is None:
                self.update_class(my_class)

            print "not parsed yet: ", self.filename
            self.update_class(my_class)
            self.save_functions(self.filename)  # parse current file

            parent_class_name = my_class.parent_class()
            parent_file = self.get_file_name(parent_class_name)
            if parent_file is not None:
                self.collector.add_function_collector_thread(parent_file)   # create a new thread to parse the parent_file too

            my_class.save_completions(self._functions, self._variables, self._consts, self._structs)

        self.stop()

    # checks the class and if there are changes, update the class declaration of to the class
    def update_class(self, my_class=None):
        description = ""
        with open(self.filename, 'rU') as file_lines:
            for line in file_lines:
                description += line
                classline = re.match(r'(class\b.+\bextends )(\b.+\b)', line.lower())  # get class declaration line of current file
                if classline is not None:
                    parent_class_name = classline.group(2)  # get parent class
                    if my_class:
                        if my_class.parent_class() != parent_class_name or my_class.description() != description:
                            my_class.update_class(parent_class_name, description)
                    else:
                        c = self.collector.add_class(os.path.basename(self.filename).split('.')[0],
                                                     parent_class_name,
                                                     description,
                                                     self.filename)
                        c.link_to_parent()
                    break

    # adds the function to _functions
    def add_func(self, function_modifiers, return_type, function_name, arguments, line_number, file_name, description="", is_funct=1):
        # if self.get_function(function_name) is None:
        if function_name != "":
            self._functions.append(Function(function_modifiers, return_type.strip(), function_name.strip(), arguments, line_number + 1, file_name, description, is_funct))

    # adds the variable to _variables
    def add_var(self, var_modifiers, var_name, comment, line_number, file_name, description="", bStruct=False):
        # if self.get_variable(var_name) is None:
        if bStruct:
            self._struct_variables.append(Variable(var_modifiers, var_name.strip(), comment, line_number + 1, file_name, description))
        else:
            self._variables.append(Variable(var_modifiers, var_name.strip(), comment, line_number + 1, file_name, description))

    def add_const(self, CONST_name, value, comment, line_number, file_name, description=""):
        self._consts.append(Const(CONST_name.strip(), value, comment, line_number + 1, file_name, description))

    def add_struct(self, struct_name, line, line_number, file_name, description):
        self._structs.append(Struct(struct_name.strip(), line, line_number + 1, file_name, description))

    # returns the filename of the given class name
    def get_file_name(self, class_name):
        parent_class = self.collector.get_class(class_name)
        if parent_class is not None:
            return parent_class.file_name()
        return None

    # extract functions, event and variables and split them into smaller groups.
    # ! TODO:   -support ENUMS
    #           -Probably rewrite this, as it is pretty ugly
    def save_functions(self, file_name):
        with open(file_name, 'rU') as file_lines:
            current_documentation = ""
            long_line = ""
            b_function = True
            bBracesNotOnSameLine = False
            bCppText = False
            CppTextBracketsNum = 0
            bStruct = False
            for i, line in enumerate(file_lines):
                if bCppText:
                    if '{' == line.strip():
                        CppTextBracketsNum += 1
                    elif '}' == line.strip():
                        CppTextBracketsNum -= 1
                    if CppTextBracketsNum == 0:
                        bCppText = False
                    continue

                if bStruct:
                    if "};" in line:
                        bStruct = False
                        self._structs[-1].save_variables(self._struct_variables)
                        self._struct_variables = []

                if line == "":
                    continue
                if "cpptext" == line.lower().strip():
                    bCppText = True

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

                if not bStruct and "struct" in line.lower():
                    if "struct" == line.lower().split()[0]:
                        bStruct = True
                        self._struct_variables = []
                        if "extends" in line.lower():
                            line = line.split("extends")[0]
                        struct_name = line.split()[-1]
                        self.add_struct(struct_name, line, i, file_name, current_documentation)

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

                    else:   # epic fail of my regex, try with python or function / event was in the comments:
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
                        self.add_var(var_line, name, doc_line, i, file_name, current_documentation, bStruct)
                    current_documentation = ""

                elif "const" in line.lower():
                    const_doc_line = line.split('//')
                    const_line = const_doc_line[0].split()
                    if const_line and "const" != const_line[0].lower():
                        continue
                    elif not const_line:
                        continue

                    if len(const_line) != 4:
                        const_line = " ".join(const_line).replace('=', " = ")
                        const_line = const_line.split()

                    doc_line = ''
                    if len(const_doc_line) > 1:
                        doc_line = const_doc_line[1].rstrip()

                    self.add_const(const_line[1], const_line[3].rstrip('\n\r\t ;'), doc_line, i, file_name, current_documentation)
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
    _consts = []
    _structs = []
    _b_was_parsed = False
    _parent_class = None
    _child_classes = []

    def __init__(self, class_name, parent_class, description, file_name, collector_reference):
        self._name = class_name
        self._description = description
        self._file_name = file_name
        self._parent_class_name = parent_class
        self._collector_reference = collector_reference

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

    def type(self):
        v_type = self._variable_modifiers[-1].strip()
        if "class<" == v_type[:6]:
            v_type = "class"
        elif "array<" == v_type[:6]:
            v_type = "array"
        return v_type

    def secondary_type(self):
        v_type = self._variable_modifiers[-1].strip()
        if "class<" == v_type[:6]:
            v_type = v_type[6:-1].strip()
        elif "array<" == v_type[:6]:
            v_type = v_type[6:-1].strip()
        return v_type

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
        view.run_command("insert_snippet", {"contents": (Object_Name % {"name": self._name})})

    def create_dynamic_tooltip(self, view):
        documentation = self.description() + self.var_modifiers() + self.name() + ";" + (" //" + self.comment() if self.comment() != "" else "")
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
        return self._comment

    def name(self):
        return self._name.strip()

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
        documentation = self.description() + "CONST " + self.name() + " = " + self.value() + ";" + (" //" + self.comment() if self.comment() != "" else "")
        print_to_panel(view, documentation)


# --------------------------------
# Dynamic Snippets
# ----------------

Function_Snippet_Declaration = \
"""%(description)s%(function_modifiers)s%(return_type)s%(funct)s %(function_name)s(%(arguments)s)
{
    ${2:super.%(function_name)s(%(less_arguments)s);}
    ${3://}
}"""

Function_Snippet_Call = \
"""%(function_name)s(%(arguments)s)"""

Object_Name = \
"""%(name)s"""


########################################################
#Event
#-----
# this one is taken from: http://www.valuedlessons.com/2008/04/events-in-python.html
########################################################
class Event:
    def __init__(self):
        self.handlers = set()

    def handle(self, handler):
        self.handlers.add(handler)
        return self

    def unhandle(self, handler):
        try:
            self.handlers.remove(handler)
        except:
            raise ValueError("Handler is not handling this event, so cannot unhandle it.")
        return self

    def fire(self, *args, **kargs):
        for handler in self.handlers:
            handler(*args, **kargs)

    def getHandlerCount(self):
        return len(self.handlers)

    __iadd__ = handle
    __isub__ = unhandle
    __call__ = fire
    __len__ = getHandlerCount


class EventManager():
    def __init__(self):
        # self.parsing_finished = Event()
        self.go_to_definition = Event()
        self.rebuild_cache = Event()


# def on_parsing_finished(self, arg):
#     print arg

# evt_m().parsing_finished += self.on_parsing_finished

unreal_keywords = ["abstract", "array", "arraycount", "assert", "auto", "automated", "bool", "break", "button",
                   "byte", "coerce", "collapsecategories", "config", "const", "continue", "default", "delegate",
                   "dependson", "deprecated", "dontcollapsecategories", "edfindable", "editconst", "editconstarray",
                   "editinline", "editinlinenew", "editinlinenotify", "editinlineuse", "enumcount", "event", "exec",
                   "expands", "export", "exportstructs", "extends", "final", "float", "global", "globalconfig",
                   "goto", "guid", "hidecategories", "ignores", "import", "init", "input", "insert", "instanced",
                   "int", "intrinsic", "iterator", "latent", "length", "local", "localized", "name", "new", "noexport",
                   "none", "noteditinlinenew", "notplaceable", "nousercreate", "operator", "optional", "out",
                   "perobjectconfig", "placeable", "pointer", "postoperator", "preoperator", "private", "protected",
                   "reliable", "remove", "return", "rot", "safereplace", "self", "showcategories", "simulated", "singular",
                   "state", "static", "string", "super", "transient", "travel", "unreliable", "var", "vect", "Repnotify", "Client",
                   "Server", "AutoExpandCategories", "implements", "Inherits", "NonTransient", "StructDefaultProperties",
                   "if", "else", "class", "DefaultProperties", "do", "until", "enum", "for", "false", "true", "foreach",
                   "function", "struct", "switch", "while"]
