#-----------------------------------------------------------------------------------
# UnrealScriptIDE Parser
#-----------------------------------------------------------------------------------
#
#   The parser reads in all files inside the src folder and creates the classes data.
#   When a class is needed for auto-completion it will parse this class and all its parent classes.
#
# ! TODO:
#       -enum support
#       -live parsing of current file.
#       -local variable support
#
# (c) Florian Zinggeler
#-----------------------------------------------------------------------------------
import sublime
import threading
import UnrealScriptIDEData as USData
import re
import os


# Adds the class inside (filename) to the collector.
# if b_first is true, creates a thread for every file in the src directory
class ClassesCollectorThread(threading.Thread):
    def __init__(self, collector, filename, timeout_seconds, open_folder_arr, b_first=False):
        self.collector = collector
        self.timeout = timeout_seconds
        self.filename = filename
        self.open_folder_arr = open_folder_arr
        self.b_first = b_first
        self.inbuild_classes = ["Array", "Class", "HiddenFunctions"]
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
                        self.get_classes(f)
                        self.get_inbuilt_classes()
                    break
            self.stop()

        else:
            if self.filename is not None:
                self.save_classes()
                self.stop()

    # creates a new thread for every file in the src directory
    def get_classes(self, path):
        for file in os.listdir(path):
            dirfile = os.path.join(path, file)
            if os.path.isfile(dirfile) and dirfile.endswith(".uc"):
                    self.collector._collector_threads.append(ClassesCollectorThread(self.collector, dirfile, 30, self.open_folder_arr))
                    self.collector._collector_threads[-1].start()

            elif os.path.isdir(dirfile):
                self.get_classes(dirfile)

    def get_inbuilt_classes(self):
        for f in self.inbuild_classes:
            path = os.path.join(sublime.packages_path(), "UnrealScriptIDE\\InbuiltClasses\\" + f + ".uc")
            self.collector._collector_threads.append(ClassesCollectorThread(self.collector, path, 30, self.open_folder_arr))
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
                elif "*" not in line[:3] and "/" not in line[:3]:
                    if any(["class " + cls.lower() in line.lower() for cls in self.inbuild_classes] + ["class object" in line.lower()]):
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
class ParserThread(threading.Thread):
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
                        
                        try:
                            c.link_to_parent()
                        except AttributeError:
                            print "Something is wrong, better rebuild the cache."
                            self.view.window().run_command("unreal_rebuild_cache")
                    break

    # adds the function to _functions
    def add_func(self, function_modifiers, return_type, function_name, arguments, line_number, file_name, description="", is_funct=1):
        # if self.get_function(function_name) is None:
        if function_name != "":
            self._functions.append(USData.Function(function_modifiers.strip(), return_type.strip(), function_name.strip(), arguments.strip(), line_number + 1, file_name, description, is_funct))

    # adds the variable to _variables
    def add_var(self, var_modifiers, var_name, comment, line_number, file_name, description="", bStruct=False):
        # if self.get_variable(var_name) is None:
        if bStruct:
            self._struct_variables.append(USData.Variable(var_modifiers, var_name.strip(), comment, line_number + 1, file_name, description))
        else:
            self._variables.append(USData.Variable(var_modifiers, var_name.strip(), comment, line_number + 1, file_name, description))

    def add_const(self, CONST_name, value, comment, line_number, file_name, description=""):
        self._consts.append(USData.Const(CONST_name.strip(), value, comment, line_number + 1, file_name, description))

    def add_struct(self, struct_name, line, line_number, file_name, description):
        self._structs.append(USData.Struct(struct_name.strip(), line, line_number + 1, file_name, description))

    # returns the filename of the given class name
    def get_file_name(self, class_name):
        parent_class = self.collector.get_class(class_name)
        if parent_class is not None:
            return parent_class.file_name()
        return None

    # extract functions, event and variables and split them into smaller groups.
    # ! TODO:   -support ENUMS
    def save_functions(self, file_name):
        with open(file_name, 'rU') as file_lines:
            current_documentation = ""
            long_line = ""
            bBracesNotOnSameLine = False
            bCppText = False
            CppTextBracketsNum = 0
            bStruct = False
            regex_f = re.compile(r"([a-zA-Z0-9()\s]*?)function[\s]+((coerce)\s*)?([a-zA-z0-9<>_]*?)[\s]*([a-zA-z0-9_-]+)([\s]*\(+)(.*)((\s*\))+)[\s]*(const)?[\s]*;?[\s]*(\/\/.*)?")
            regex_e = re.compile(r"([a-zA-Z0-9()\s]*?)event[\s]+((coerce)\s*)?([a-zA-z0-9<>_]*?)[\s]*([a-zA-z0-9_-]+)([\s]*\(+)(.*)((\s*\))+)[\s]*(const)?[\s]*;?[\s]*(\/\/.*)?")
            regex_c = re.compile(r"const[\s]+([a-zA-Z0-9_]+)[\s]*=[\s]*([a-zA-Z0-9\"'!_\-.]+);")

            for i, line in enumerate(file_lines):
                if line.strip() == "":
                    current_documentation = ""
                    continue

                # skip lines inside cpptext.
                if bCppText:
                    if '{' == line.strip():
                        CppTextBracketsNum += 1
                    elif '}' == line.strip():
                        CppTextBracketsNum -= 1
                    if CppTextBracketsNum == 0:
                        bCppText = False
                    continue

                if bStruct:
                    # struct finished, save variables to struct.
                    if "};" in line:
                        bStruct = False
                        self._structs[-1].save_variables(self._struct_variables)
                        self._struct_variables = []

                if "cpptext" == line.lower().strip():
                    bCppText = True

                if "/*" == line.lstrip()[:2]:                       # start capturing documentation
                    current_documentation = line
                    continue
                elif "/" == line.lstrip()[0] and current_documentation == "":
                    current_documentation = line
                    continue

                if current_documentation != "":     # add to documentation
                    if current_documentation != line:
                        current_documentation += line
                if line.lstrip()[0] == '*' or line.lstrip()[:2] == "//":
                    continue

                left_line = line.split('//')[0].lower()
                if bBracesNotOnSameLine:
                    if ')' in left_line:
                        bBracesNotOnSameLine = False
                        new_line = ' '.join(long_line.split()) + ')'
                        if not self.extract_functions(new_line, new_line, i, file_name, current_documentation, regex_f, regex_e):
                            if not self.extract_comlicated_function(new_line, new_line, i, file_name, current_documentation, regex_f, regex_e):
                                print "Failed to parse this function/event:\n", new_line, "\n(it probably should fail. If you see a line that fails that shouldn't, contact me)"
                            # if "event final Inventory CreateInventory( class<Inventory> NewInvClass, optional bool bDoNotActivate ) {)" == new_line:
                            #     self.add_func("", "Inventory", "CreateInventory", "class<Inventory> NewInvClass, optional bool bDoNotActivate", i, file_name, current_documentation, False)
                            # elif "native noexport final function coerce actor Spawn ( class<actor> SpawnClass, optional actor SpawnOwner, optional name SpawnTag, optional vector SpawnLocation, optional rotator SpawnRotation, optional Actor ActorTemplate, optional bool bNoCollisionFail)" in new_line:
                            #     self.add_func("native noexport final ", "actor", "Spawn", "class<actor> SpawnClass, optional actor SpawnOwner, optional name SpawnTag, optional vector SpawnLocation, optional rotator SpawnRotation, optional Actor ActorTemplate, optional bool bNoCollisionFail", i, file_name, current_documentation, False)
                        current_documentation = ""
                        continue
                    else:
                        long_line += line

                if not bStruct and "struct" in left_line:
                    if "struct" == left_line.split()[0]:
                        bStruct = True
                        self._struct_variables = []
                        if "extends" in left_line:
                            line = line.split("extends")[0]
                        struct_name = line.split()[-1]
                        self.add_struct(struct_name, line, i, file_name, current_documentation)
                        current_documentation = ""

                if "function" in left_line or "event" in left_line:  # get possible lines containing functions / events
                    if self.extract_functions(line, left_line, i, file_name, current_documentation, regex_f, regex_e):
                        current_documentation = ""
                    else:   # fail to capture function, check if it should really fail or if it is a function on multiple lines:
                        b_fail = True
                        for i, txt in enumerate(left_line.split()):
                            if txt.lower() == "function" or txt.lower() == "event":
                                b_fail = False
                                if '(' in left_line.split()[i:] and ')' in left_line.split()[i:]:
                                    print "Failed to parse this function/event:\n", line, "(it probably should fail. If you see a line that fails that shouldn't, contact me)"
                                    b_fail = True
                                    continue
                                continue
                        if not b_fail:
                            bBracesNotOnSameLine = True
                            long_line = line

                elif "var" in left_line:  # get possible lines containing variables
                    # 1: vartype, 2: name, 3: documentation
                    var_doc_line = line.split('//')
                    if len(var_doc_line) < 2:
                        var_doc_line = line.split('/**')
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
                        if "<" in name or ">" in name:
                            name = re.sub(r'\<.*?\>', '', name)
                        self.add_var(var_line, name, doc_line, i, file_name, current_documentation, bStruct)
                    current_documentation = ""

                elif "const" in left_line:
                    if self.extract_const(line, i, file_name, current_documentation, regex_c):
                        current_documentation = ""
                    else:   # fail to capture const
                        print "Failed to parse const:\n", line, "(it probably should fail. If you see a line that fails that shouldn't, contact me)"

    # get the function in left_line. If this failed return false
    def extract_functions(self, line, left_line, i, file_name, current_documentation, regex_f, regex_e):
        if "function" in left_line.lower():
            b_function = True
            regex = regex_f
        elif "event" in left_line.lower():
            b_function = False
            regex = regex_e
        else:
            print "No function or event in ", left_line.lower(), "   . full line: ", line
            return False

        matches = regex.search(line.strip())    # search for:  1: modifiers, 2: return type, 3: name, 4: arguments, 5: const, 6: comment
        if matches is not None:
            self.add_func(matches.group(1), matches.group(4), matches.group(5), matches.group(7), i, file_name, current_documentation, b_function)
            return True

    def extract_comlicated_function(self, line, left_line, i, file_name, current_documentation, regex_f, regex_e):
        # "event final Inventory CreateInventory( class<Inventory> NewInvClass, optional bool bDoNotActivate ) {)"
        b_function = False
        if "function" in left_line.lower():
            new_line = re.split('function(?i)', left_line)
            b_function = True
        elif "event" in left_line.lower():
            new_line = re.split('event(?i)', left_line)
        new_line = new_line[0] + (" function " if b_function else " event ") + " ".join(new_line[-1].strip().split()[1:])
        return self.extract_functions(new_line, new_line, i, file_name, current_documentation, regex_f, regex_e)

    def extract_const(self, line, i, file_name, current_documentation, regex_c):
        comment = line.split('//')[-1]
        matches = regex_c.search(line.strip())    # search for:  1: name, 2: value
        if matches is not None:
            self.add_const(matches.group(1), matches.group(2), comment, i, file_name, current_documentation)
            return True
        return False

    def stop(self):
        if self.isAlive():
            self._Thread__stop()
