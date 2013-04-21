#------------------------------------------------------------------------------
# UnrealScriptIDE UnrealDebugger integration
#------------------------------------------------------------------------------
#
#   -installs the debugger automatically when you build with a debug configuration. Preserves other installed debugger.
#   -adds a command to uninstall the debugger and restore your old debugger.
#   -set breakpoint inside Sublime:
#
#   (TODO):
#       sync opened files
#
# (c) Florian Zinggeler
#------------------------------------------------------------------------------
import sublime
import sublime_plugin
import os
import threading
import shutil
from xml.etree import ElementTree


def get_paths(open_folder_arr, b_64bit=False):
    # search open folders for the Src directory
    for folder in open_folder_arr:
        if "\Development\Src" in folder:
            udk_exe_path = folder
            break
    if udk_exe_path == "":
        print "Src folder not found!!!"
        return

    # Removing "Development\Src" (this is probably not how it's done correctly):
    udk_path = udk_exe_path[:-15]
    if b_64bit:
        install_dir = udk_path + "Binaries\\Win64\\"
        source_dir = sublime.packages_path() + "\\UnrealScriptIDE\\Debugger\\UnrealDebugger 64 bits"
    else:
        install_dir = udk_path + "Binaries\\Win32\\"
        source_dir = sublime.packages_path() + "\\UnrealScriptIDE\\Debugger\\UnrealDebugger 32 bits"
    return [install_dir, source_dir]


# Installs the debugger. if there is already a debugger installed, creates a backup
class UnrealInstallDebuggerCommand(sublime_plugin.TextCommand):
    def run(self, edit, b_64bit=False):
        open_folder_arr = self.view.window().folders()   # Gets all opened folders in the Sublime Text editor.
        self.install_dir, self.source_dir = get_paths(open_folder_arr, b_64bit)
        self.install_debugger()

    # copies all needed files and if needed creates a backup of DebuggerInterface.dll
    def install_debugger(self):
        for filename in os.listdir(self.source_dir):
            try:
                if os.path.getsize(os.path.join(self.source_dir, filename)) != os.path.getsize(os.path.join(self.install_dir, filename)):
                    # backup
                    if filename == "DebuggerInterface.dll":
                        if not os.path.exists(os.path.join(self.install_dir, "DebuggerInterface.dll-old-UScriptIDE")):
                            print "Another debugger was found. Creating backup"
                            os.rename(os.path.join(self.install_dir, filename), os.path.join(self.install_dir, "DebuggerInterface.dll-old-UScriptIDE"))
                    # install
                    print "install newer version", filename
                    self.install(os.path.join(self.source_dir, filename), os.path.join(self.install_dir, filename))
            except os.error:
                # install
                print "fresh install", filename
                self.install(os.path.join(self.source_dir, filename), os.path.join(self.install_dir, filename))
        self.view.window().run_command("unreal_load_breakpoints", {"b_set_breakpoints": True})

    # copy file or directory
    def install(self, src, dst):
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy(src, dst)


# Uninstalls the debugger and install your old debugger again
class UnrealUninstallDebuggerCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        open_folder_arr = self.view.window().folders()   # Gets all opened folders in the Sublime Text editor.
        self.install_dir_32, self.source_dir_32 = get_paths(open_folder_arr, False)
        self.install_dir_64, self.source_dir_64 = get_paths(open_folder_arr, True)
        self.uninstall(self.source_dir_32, self.install_dir_32)
        self.uninstall(self.source_dir_64, self.install_dir_64)

    # deletes all debugger files and restores the backup
    def uninstall(self, src, uninst):
        print "uninstall debugger from ", uninst
        for f in os.listdir(src):
            uninst_f_path = os.path.join(uninst, f)
            if os.path.exists(uninst_f_path):
                if os.path.isfile(uninst_f_path):
                    os.unlink(uninst_f_path)
                else:
                    shutil.rmtree(uninst_f_path)
        backup = os.path.join(uninst, "DebuggerInterface.dll-old-UScriptIDE")
        if os.path.exists(backup):
            if not os.path.exists(backup[:-15]):
                print "old debugger found, reinstalling the debugger"
                os.rename(backup, backup[:-15])


class UnrealLoadBreakpointsCommand(sublime_plugin.TextCommand):
    def run(self, edit, b_set_breakpoints=False):
        self.filename = self.view.file_name()
        if self.filename:
            open_folder_arr = self.view.window().folders()
            install_dir_64, src_dir = get_paths(open_folder_arr, True)
            install_dir_32, src_dir = get_paths(open_folder_arr, False)
            self.breakpoints_xml = install_dir_64[:-6] + "UScriptIDE_Breakpoints.xml"

            if os.path.exists(self.breakpoints_xml):
                xml_tree = ElementTree.parse(self.breakpoints_xml)
                breakpoints = xml_tree.find("Breakpoints")
                if b_set_breakpoints:
                    print "set breakpoints"
                    self.set_breakpoints(breakpoints, install_dir_32 + "UnrealDebugger.project")
                    self.set_breakpoints(breakpoints, install_dir_64 + "UnrealDebugger.project")
                else:
                    print "load breakpoints"
                    LoadBreakpoints(breakpoints, self).start()
                    # self.load_breakpoints(breakpoints)

    def call_toggle_breakpoint(self, b):
        p = self.view.text_point(int(b.find("LineNo").text)-1, 0)
        point = self.view.line(p)
        self.view.window().run_command("unreal_toggle_breakpoint", {"b_deactivate": b.find("Enabled").text != "true", "breakpoint_a": point.a, "breakpoint_b": point.b})

    # copies the breakpoints from the master file to The Debugger files
    def set_breakpoints(self, breakpoints, debugger_file):
        if os.path.exists(debugger_file):
            debugger_tree = ElementTree.parse(debugger_file)
            debugger_breakpoints = debugger_tree.find("Breakpoints")
            dic = breakpoints.find("Dictionary")
            dic_debug = debugger_breakpoints.find("Dictionary")
            dic_debug.clear()
            for item in dic:
                dic_debug.append(item)
            debugger_tree.write(debugger_file)
        else:
            shutil.copy(self.breakpoints_xml, debugger_file)


class LoadBreakpoints(threading.Thread):
    def __init__(self, breakpoints, main_thread):
        self.breakpoints = breakpoints
        self.main_thread = main_thread
        threading.Thread.__init__(self)

    def run(self):  # gets called when the thread is created
        self.load_breakpoints(self.breakpoints)
        self.stop()

    def stop(self):
        if self.isAlive():
            self._Thread__stop()

    # loads the saved breakpoints from the master file to the current view
    def load_breakpoints(self, breakpoints):
        dic = breakpoints.find("Dictionary")
        current_file = self.main_thread.filename.split('\\')[-1].split('.')[0].lower()
        for item in dic:
            k = item.find("key")
            s = k.find("string")
            if s.text.split('.')[-1].lower() == current_file:
                print "load breakpoints for file ", current_file
                v = item.find("value")
                arr = v.find("ArrayOfBreakpoint")
                for b in arr:
                    # p = self.main_thread.view.text_point(int(b.find("LineNo").text)-1, 0)
                    # point = self.main_thread.view.line(p)
                    print ElementTree.tostring(b)
                    sublime.set_timeout(lambda: self.main_thread.call_toggle_breakpoint(b), 1000)


# Toggles a breakpoint visually. Also saves the breakpoints to the master file.
class UnrealToggleBreakpointCommand(sublime_plugin.TextCommand):
    def run(self, edit, b_deactivate=False, breakpoint_a=None, breakpoint_b=None):
        old_breakpoints = self.view.get_regions("breakpoint_enabled")
        old_breakpoints_deactivated = self.view.get_regions("breakpoint_deactivated")

        if breakpoint_a and breakpoint_b:
            print breakpoint_a, breakpoint_b, b_deactivate
            breakpoint = [sublime.Region(breakpoint_a, breakpoint_b)]
            if breakpoint[0] not in old_breakpoints and breakpoint[0] not in old_breakpoints_deactivated:
                if not b_deactivate:
                    self.view.add_regions("breakpoint_enabled", old_breakpoints + breakpoint, "breakpoint", "circle", sublime.HIDDEN | sublime.PERSISTENT)
                else:
                    self.view.add_regions("breakpoint_deactivated", old_breakpoints_deactivated + breakpoint, "breakpoint", "dirty_circle_light", sublime.HIDDEN | sublime.PERSISTENT)
        else:
            selections = [s for s in self.view.sel()]
            selections = self.clean_selection(selections)

            if not b_deactivate:
                new_breakpoints = self.create_new_breakpoints(old_breakpoints, selections)
                new_breakpoints_deactivated = self.list_minus_list(old_breakpoints_deactivated, new_breakpoints)
            else:
                new_breakpoints_deactivated = self.create_new_deactivated_breakpoints(old_breakpoints, selections)
                new_breakpoints_deactivated += old_breakpoints_deactivated
                new_breakpoints = self.list_minus_list(old_breakpoints, new_breakpoints_deactivated)

            self.view.add_regions("breakpoint_deactivated", new_breakpoints_deactivated, "breakpoint", "dirty_circle_light", sublime.HIDDEN | sublime.PERSISTENT)  # dirty_indicator, dirty_circle, circle
            self.view.add_regions("breakpoint_enabled", new_breakpoints, "breakpoint", "circle", sublime.HIDDEN | sublime.PERSISTENT)
            self.save_breakpoints(new_breakpoints, new_breakpoints_deactivated)

    # this saves the currently only visual breakpoints to the master file
    def save_breakpoints(self, breakpoints, breakpoints_deactivated):
        self.current_file = self.view.file_name().split('\\')
        self.current_file = self.current_file[-3] + "." + self.current_file[-1].split('.')[0]

        breakpoints_formatted = []
        for b in breakpoints:
            line, c = self.view.rowcol(b.a)
            breakpoints_formatted.append((line + 1, True))
        for b in breakpoints_deactivated:
            line, c = self.view.rowcol(b.a)
            breakpoints_formatted.append((line + 1, False))
        print breakpoints_formatted

        open_folder_arr = self.view.window().folders()
        install_dir_64, src_dir = get_paths(open_folder_arr, True)
        breakpoints_xml = install_dir_64[:-6] + "UScriptIDE_Breakpoints.xml"

        if os.path.exists(breakpoints_xml):
            print "append breakpoints to existing xml"
            xml_tree = ElementTree.parse(breakpoints_xml)
            bs = xml_tree.find("Breakpoints")
            d = bs.find('Dictionary')
            b_found_item = False
            for item in d:
                if item[0][0].text == self.current_file.upper():
                    item[1][0].clear()
                    b_found_item = True
                    self.add_breakpoints_to_array(breakpoints_formatted, item[1][0])
            if not b_found_item:
                arr = self.add_item_to_dictionary(d)
                self.add_breakpoints_to_array(breakpoints_formatted, arr)
            xml_tree.write(breakpoints_xml)
        else:
            print "create new xml with breakpoints"
            root = ElementTree.Element('Project')
            bs = ElementTree.SubElement(root, "Breakpoints")
            d = ElementTree.SubElement(bs, "Dictionary")
            arr = self.add_item_to_dictionary(d)
            self.add_breakpoints_to_array(breakpoints_formatted, arr)
            ElementTree.ElementTree(root).write(breakpoints_xml)

    def add_item_to_dictionary(self, Dictionary):
        i = ElementTree.SubElement(Dictionary, "item")
        k = ElementTree.SubElement(i, "key")
        s = ElementTree.SubElement(k, "string")
        s.text = self.current_file.upper()
        v = ElementTree.SubElement(i, "value")
        return ElementTree.SubElement(v, "ArrayOfBreakpoint")

    def add_breakpoints_to_array(self, breakpoints_formatted, ArrayOfBreakpoint):
        for point in breakpoints_formatted:
            b = ElementTree.SubElement(ArrayOfBreakpoint, "Breakpoint")
            cn = ElementTree.SubElement(b, "ClassName")
            cn.text = self.current_file
            ln = ElementTree.SubElement(b, "LineNo")
            ln.text = str(point[0])
            h = ElementTree.SubElement(b, "Healthy")
            h.text = str(point[1]).lower()
            e = ElementTree.SubElement(b, "Enabled")
            e.text = str(point[1]).lower()

    # this will return the new breakpoints. If a breakpoint in new_candidates is already in old_breakpoints it will be removed.
    def create_new_breakpoints(self, old_breakpoints, new_candidates):
        new_breakpoints = []
        for b in old_breakpoints:
            if b in new_candidates:
                new_candidates.remove(b)
            else:
                new_breakpoints.append(b)
        new_breakpoints += new_candidates
        return new_breakpoints

    # returns all matching breakpoints
    def create_new_deactivated_breakpoints(self, old_breakpoints, new_candidates):
        new_breakpoints = []
        for b in old_breakpoints:
            if b in new_candidates:
                new_breakpoints.append(b)
        return new_breakpoints

    def list_minus_list(self, a, b):
        for x in b:
            if x in a:
                a.remove(x)
        return a

    def clean_selection(self, selection):
        new_candidates_cleaned = []
        for s in selection:
            new_candidates_cleaned += self.view.split_by_newlines(s)
        selection = []
        for r in new_candidates_cleaned:
            selection.append(self.view.line(r))
        return selection
