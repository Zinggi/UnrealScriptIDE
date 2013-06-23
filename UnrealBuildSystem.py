#------------------------------------------------------------------------------
# UnrealScriptIDE build system
#------------------------------------------------------------------------------
#
#   This script searches the UDK.exe based on the Src path.
#   It can compile your project and start the game with a specified map.
#   If the build contains errors, an error summary / log will open.
#   If the build contains only warnings, you will be asked to either open the log or start the game.
#
# (c) Florian Zinggeler
#------------------------------------------------------------------------------
import sublime
import sublime_plugin
import subprocess
import threading
import time
import os
from UnrealScriptIDEData import print_to_panel


# Builds your udk project and gets the output.
class UnrealBuildProjectCommand(sublime_plugin.TextCommand):
    udk_path = ""
    udk_exe_path = ""
    udkLift_exe_path = ""
    udk_maps_folder = []
    # the building output
    _output = []
    # there were some errors
    _b_open_output = False
    # there were just warnings
    _b_ask_if_open_output = False

    _last_opened_map = ""
    _selected_map = ""

    b_build_and_run = False
    b_compiled_debug = False

    compile_settings = []

    # all startup configurations
    startup_configurations = []
    # the key of one startup configurations
    last_used_configuration = ""

    # find src folder and start building
    def run(self, edit, b_build_and_run=False, b_show_compile_options=False):
        self._b_open_output = False
        self._b_ask_if_open_output = False
        if self.view.file_name() is not None:
            self.settings = sublime.load_settings('UnrealScriptIDE.sublime-settings')
            self.b_build_and_run = b_build_and_run
            self.udk_maps_folder = []
            project_folders = self.view.window().folders()   # Gets all opened folders in the Sublime Text editor.
            all_folders = []

            # sub_folders also contains the parent folder, no worries.
            for folder in project_folders:
                sub_folders = [x[0] for x in os.walk(folder)]
                all_folders += sub_folders

            # search open folders for the Src directory
            for folder in all_folders:
                if folder.endswith("\Development\Src"):
                    self.udk_exe_path = folder
                    break
            if self.udk_exe_path == "":
                print "Src folder not found!!!"
                return

            # Removing "Development\Src" and adding the UDK.com path (this is probably not how it's done correctly):
            self.udk_path = self.udk_exe_path[:-15]
            self.udkLift_exe_path = self.udk_path + "Binaries\\UDKLift.exe"
            map_folders = self.settings.get('map_folders')
            for f in map_folders:
                if f[1] != ':':
                    self.udk_maps_folder.append(self.udk_path + f)
                else:
                    self.udk_maps_folder.append(f)
            # self.udk_maps_folder = self.udk_path + "UDKGame\\Content\\Maps"

            if not b_show_compile_options:
                compile_settings_key = self.settings.get('current_compile_settings')
                self.compile_settings = self.settings.get('compiling_configurations')[compile_settings_key]
                self.udk_exe_path = self.udk_path + "Binaries\\" + self.compile_settings[0]
                self.start_build()

            else:
                self.show_compile_options()

            # self.udk_exe_path = self.udk_exe_path[:-15] + "Binaries\\Win32\\UDK.com"
            # self.udkLift_exe_path = self.udk_exe_path[:-13] + "UDKLift.exe"
            # self.udk_maps_folder = self.udk_exe_path[:-22] + "UDKGame\\Content\\Maps"

    # starts building your game. This adds a new UDKbuild thread.
    def start_build(self):
        if self.settings.get( 'save_all_on_build' ) == True:
            self.save_all_scripts()
        
        self._output = []
        self._build_thread = UDKbuild(self.udk_exe_path, self)
        self._build_thread.start()
        self.handle_thread()

    def save_all_scripts(self):
        for view in self.view.window().views():
            if view.is_dirty() and not view.is_read_only():
                is_script = view.settings().get('syntax').endswith( "UnrealScriptIDE/UnrealScript.tmLanguage" )
                if is_script:
                    view.run_command( 'save' )

    def show_compile_options(self):
        self.compile_settings = self.settings.get('compiling_configurations')

        self.input_list = [["Full recompile with last used configuration",          # ["Compile with last used configuration", self.settings.get('current_compile_settings')],
                            self.settings.get('current_compile_settings')]]

        for config in self.compile_settings:
            self.input_list.append([config] + self.compile_settings[config])

        self.view.window().show_quick_panel(self.input_list, self.on_done_chose_compile_setting)

    def on_done_chose_compile_setting(self, index):
        # if index == 0:
        #     self.compile_settings = self.compile_settings[self.settings.get('current_compile_settings')]
        #     self.udk_exe_path = self.udk_path + "Binaries\\" + self.compile_settings[0]
        #     self.start_build()
        if index == 0:
            self.compile_settings = self.compile_settings[self.settings.get('current_compile_settings')]
            self.compile_settings[1] += " -full"
            self.udk_exe_path = self.udk_path + "Binaries\\" + self.compile_settings[0]
            self.start_build()
        elif index == -1:
            return
        else:
            key = self.input_list[index][0]
            self.compile_settings = self.compile_settings[key]
            self.settings.set('current_compile_settings', key)
            sublime.save_settings('UnrealScriptIDE.sublime-settings')
            self.show_compile_options()

    # display a progress icon at the bottom while building.
    # Once finished, this opens the log, starts the game or ask you what to do.
    def handle_thread(self, i=0, dir=1):
        if self._build_thread and not self._build_thread.isAlive():
            self._build_thread = None

        # while it is building..
        if self._build_thread:
            # This animates a little activity indicator in the status area
            before = i % 8
            after = (7) - before
            if not after:
                dir = -1
            if not before:
                dir = 1
            i += dir
            self.view.set_status('UnrealScript build', 'UnrealScriptIDE is building your project [%s=%s]' % (' ' * before, ' ' * after))

            sublime.set_timeout(lambda: self.handle_thread(i, dir), 100)
            return

        # when finished, show output. b_build_and_run is set to true, just start last opened map:
        else:
            self.view.erase_status('UnrealScript build')

            # == there were building errors, display log
            if self._b_open_output:
                self.show_error_panel()
                self._b_open_output = False

            # == there were only warnings, ask what to do
            elif self._b_ask_if_open_output and not self.b_build_and_run:
                if self.settings.get('always_open_log'):
                    self.show_error_panel()
                    return
                if self.settings.get('always_start_game'):
                    self.run_game()
                    return

                input_list = ["Successfully compiled with Warnings, open the building log?",

                                "Don't open log, run the game anyway!",

                                ["Always open log. Never ask again!",
                                "You can reset your choice under:",
                                "'Ctrl + Shift + P' -> 'UnrealScriptIDE: Settings - User'"],

                                ["Always open game. Never ask for log again!",
                                "You can reset your choice under:",
                                "'Ctrl + Shift + P' -> 'UnrealScriptIDE: Settings - User'"]]
                self.view.window().show_quick_panel(input_list, self.on_done_warnings_input)

                self._b_ask_if_open_output = False

            # == no warnings and no errors, start the game.
            else:
                self.run_game()

    # shows the building error log, with summery at the top
    def show_error_panel(self, b_only_save_log=False):
        log_cache = os.path.join(sublime.packages_path(), "UnrealScriptIDE\\log_cache.log")
        with open(log_cache, 'w') as log:
            log_massage = "==============\nBUILD RESULTS:\n==============\n\nNote:\nuse UnrealScript Goto Definition to navigate to errors. (by default with f10, alt + LMB, context menu or via 'Goto' -> 'UnrealScript Goto Declaration')\n----------------------------------------------\n\n"
            log_massage += self.get_summery()
            log_massage += "\n\n\n\n\n\n\n\n\n\n\n----------------------------------------------\nFull log:\n----------------------------------------------\n\n\n"
            log_massage += "\n".join(self._output)
            log.write(log_massage)
        if not b_only_save_log:
            sublime.active_window().open_file(log_cache)
            sublime.active_window().open_file(log_cache)

    # gets called from the warning input panel
    def on_done_warnings_input(self, index):
        # 0 = open log, 1 = run game, 2 = always log, 3 = always run game, -1 = was canceled
        if index == 0:
            self.show_error_panel()
        elif index == 1:
            self.show_error_panel(True)
            self.run_game()
        elif index == 2:
            self.settings.set('always_open_log', True)
            sublime.save_settings('UnrealScriptIDE.sublime-settings')
            self.show_error_panel()

        elif index == 3:
            self.settings.set('always_start_game', True)
            sublime.save_settings('UnrealScriptIDE.sublime-settings')
            self.show_error_panel(True)
            self.run_game()
        elif index == -1:
            pass
        else:
            print "case not handled!!!"

    # Ask the user to enter a start map to start the game.
    # ask which configuration to use.
    def run_game(self):
        if self._last_opened_map == "":
            self._last_opened_map = self.settings.get('last_opened_map')

        self.last_used_configuration = self.settings.get('last_used_configuration')

        if self.b_build_and_run:
            self.on_done_run_game_input(0)
            return

        input_list = [["Start with last opened map",
                        self._last_opened_map + "\t configuration: " + self.last_used_configuration],
                        "Start with default map"]
        # add all maps found in the maps folder.
        self._map_list = self.search_mapfiles(self.udk_maps_folder)
        if not self._map_list:
            print "No maps found!!!"
            return
        input_list += self._map_list

        self.view.window().show_quick_panel(input_list, self.on_done_run_game_input)

    # gets called from the run_game input. Opens the chosen map.
    def on_done_run_game_input(self, index):
        self.startup_configurations = self.settings.get('startup_configurations')

        # 0 = open last map, 1 = open default, else: open map index, -1 = was canceled
        if index == 0:
            self.launch_game(self.last_used_configuration)
        elif index == 1:
            subprocess.Popen([self.udkLift_exe_path])
        elif index == -1:
            pass
        else:
            self.last_index = index
            self._selected_map = self._map_list[index - 2][0]

            self.input_list =   [["Start with last used Configuration", self.last_used_configuration],
                                ["Manage Configurations",
                                "This allows you to add, edit or remove startup configurations.",
                                "This can also be done in the settings:",
                                "'Ctrl + Shift + P' -> 'UnrealScriptIDE: Settings - User'"]]
            for config in self.startup_configurations:
                if "debug" in config.lower() and not self.b_compiled_debug:
                    continue
                self.input_list.append([config] + self.startup_configurations[config])

            self.view.window().show_quick_panel(self.input_list, self.on_done_chose_configuration)

    def on_done_chose_configuration(self, index):
        if index == 0:
            self.launch_game(self.last_used_configuration, self._selected_map)
        elif index == 1:
            self.edit_configurations()
        # escape: go back
        elif index == -1:
            self.run_game()
        else:
            startup_configuration = self.input_list[index][0]
            self.launch_game(startup_configuration, self._selected_map)
        self.input_list = []

    def launch_game(self, configuration, map_name=None):
        if configuration in self.startup_configurations:
            startup_configuration = self.startup_configurations[configuration]
        else:
            print "specified configuration not found!  ", configuration, "\nin ", self.startup_configurations
            return

        if map_name:
            self._last_opened_map = map_name
            self.settings.set('last_opened_map', self._last_opened_map)

        self.last_used_configuration = configuration
        self.settings.set('last_used_configuration', self.last_used_configuration)
        sublime.save_settings('UnrealScriptIDE.sublime-settings')
        exe_path = self.udk_exe_path[:-3] + "exe"
        b_server = False
        for config in startup_configuration:
            if "SERVER: " == config[:8]:
                b_server = True
                args = " /C " + exe_path + " server " + self._last_opened_map + config[8:]
                subprocess.Popen(["cmd", args], creationflags=0x08000000)
                # subprocess.Popen([exe_path, "server " + self._last_opened_map + config[8:]])
            elif "LISTEN: " == config[:8]:
                b_server = True
                subprocess.Popen([exe_path, self._last_opened_map + "?listen=true" + config[8:]])
            elif "CLIENT: " == config[:8]:
                if b_server:
                    subprocess.Popen([exe_path, "127.0.0.1 " + config[8:]])
                else:
                    subprocess.Popen([exe_path, self._last_opened_map + config[8:]])
            elif "EDITOR: ":
                args = " /C " + exe_path + " editor " + self._last_opened_map + config[8:]
                subprocess.Popen(["cmd", args], creationflags=0x08000000)
                # subprocess.Popen([exe_path, "editor " + self._last_opened_map + config[8:]])
            else:
                print "something is wrong in your settings, the startup string should start with either 'SERVER: ', 'LISTEN: ' or 'CLIENT: '"

    def edit_configurations(self):
        input_list =    [["Add a new startup configuration"],
                        ["Edit an existing configuration",
                        "To edit the name of a configuration, you will have to go in the settings"],
                        ["Remove an existing configuration"]]

        self.view.window().show_quick_panel(input_list, self.on_done_edit_configurations)

    def on_done_edit_configurations(self, index):
        if index == 0:
            self.view.window().show_input_panel("enter a name for your new configuration", "", self.on_done_enter_name, None, self.on_cancel_enter_name)
        elif index == 1:
            for config in self.startup_configurations:
                self.input_list.append([config] + self.startup_configurations[config])
            self.view.window().show_quick_panel(self.input_list, self.on_done_edit_configuration)
        elif index == 2:
            for config in self.startup_configurations:
                self.input_list.append([config] + self.startup_configurations[config])
            self.view.window().show_quick_panel(self.input_list, self.on_done_remove_configuration)
        elif index == -1:
            # escape, go back.
            self.on_done_run_game_input(self.last_index)
        else:
            print "case not handled"

    def on_cancel_enter_name(self):
        self.on_done_run_game_input(self.last_index)

    def on_done_enter_name(self, name):
        if isinstance(name, basestring):
            self.current_configuration = []
            self.configuration_name = name
            input_list =    [["Start a Client"],
                            ["Start a Server"],
                            ["Start a Listen Server"]]
            self.view.window().show_quick_panel(input_list, self.on_done_enter_name)
        else:
            if name == -1:
                self.edit_configurations()
            else:
                self.configuration_client_or_server = name
                self.view.window().show_input_panel("Add a list of startup options. Don't use: editor, server, 127.0.0.1, yourmap.udk. Example: '-ResX=1920 -ResY=1080 -fullscreen'",
                                                    "", self.on_done_enter_configuration, None, self.on_cancel_settings_dialog)

    def on_done_enter_configuration(self, config):
        configuration = self.add_client_or_server(self.configuration_client_or_server)
        configuration += config
        self.current_configuration.append(configuration)

        input_list =    [["Finish and Save this configuration"],
                        ["Add a Client"],
                        ["Cancel"]]
        self.view.window().show_quick_panel(input_list, self.on_done_entered_configuration)

    def on_done_entered_configuration(self, index):
        if index == 0:
            self.startup_configurations[self.configuration_name] = self.current_configuration
            self.settings.set('startup_configurations', self.startup_configurations)
            sublime.save_settings('UnrealScriptIDE.sublime-settings')
            self.on_done_run_game_input(self.last_index)
        elif index == 1:
            self.on_done_enter_name(0)
        elif index == 2:
            self.edit_configurations()
        elif index == -1:
            self.edit_configurations()

    def on_done_remove_configuration(self, index):
        if index == -1:
            self.edit_configurations()
        else:
            config_to_remove = self.input_list[index][0]
            del self.startup_configurations[config_to_remove]
            self.settings.set('startup_configurations', self.startup_configurations)
            sublime.save_settings('UnrealScriptIDE.sublime-settings')
            self.on_done_run_game_input(self.last_index)
        self.input_list = []

    def on_done_edit_configuration(self, index):
        if index == -1:
            self.edit_configurations()
        else:
            config_to_edit = self.input_list[index][0]
            self.configuration_name = config_to_edit
            config = self.startup_configurations[config_to_edit]
            self.current_configuration = config
            self.view.window().show_quick_panel(config, self.on_done_edit_config_item)
        self.input_list = []

    def on_done_edit_config_item(self, index):
        if isinstance(index, int):
            if index == -1:
                self.edit_configurations()
            else:
                config = self.current_configuration[index]
                self.current_index = index
                if "CLIENT: " == config[:8]:
                    self.configuration_client_or_server = 0
                elif "SERVER: " == config[:8]:
                    self.configuration_client_or_server = 1
                elif "LISTEN: " == config[:8]:
                    self.configuration_client_or_server = 2
                self.view.window().show_input_panel("Modify the startup options for this " + config[:6],
                                                    config[8:], self.on_done_edit_config_item, None, self.on_cancel_settings_dialog)
        else:
            configuration = self.add_client_or_server(self.configuration_client_or_server)
            configuration += index
            self.current_configuration[self.current_index] = configuration

            self.startup_configurations[self.configuration_name] = self.current_configuration
            self.settings.set('startup_configurations', self.startup_configurations)
            sublime.save_settings('UnrealScriptIDE.sublime-settings')
            self.on_done_run_game_input(self.last_index)

    def on_cancel_settings_dialog(self):
        self.edit_configurations()

    # returns all map files in the path folder
    def search_mapfiles(self, paths):
        maps = []
        for path in paths:
            if not os.path.exists(path):
                print "maps not found in ", path
                continue
            for file in os.listdir(path):
                dirfile = os.path.join(path, file)

                if os.path.isdir(dirfile):
                    maps += self.search_mapfiles([dirfile])
                elif any(word in dirfile for word in self.settings.get('additional_map_extensions')):
                # elif ".udk" in dirfile:
                    maps.append([file, dirfile])

        return maps

    def add_client_or_server(self, index):
        configuration = ""
        if index == 0:
            configuration = "CLIENT: "
        elif index == 1:
            configuration = "SERVER: "
        elif index == 2:
            configuration = "LISTEN: "
        return configuration

    # returns the found summery in a building log file.
    def get_summery(self):
        try:
            i = self._output.index("Warning/Error Summary")
        except ValueError, e:
            print "error: couldn't find 'Warning/Error Summary'. ", e
            return ""
        return "\n".join(self._output[i:])


# Builds your project and captures the building log output
class UDKbuild(threading.Thread):
    _collector = None

    def __init__(self, exe_path, collector):
        self.exe_path = exe_path
        self._collector = collector
        self._collector.b_compiled_debug = False
        threading.Thread.__init__(self)

    def run(self):  # gets called when the thread is created
        if not os.path.exists(self.exe_path):
            print self._collector.compile_settings[0] + " not found!!!"
            self.stop()
            return
        print "compiling with: " + self._collector.compile_settings[0] + " and " + self._collector.compile_settings[1]
        args = "make " + self._collector.compile_settings[1]
        args = " /C " + self.exe_path + " " + args  # + " -unattended"
        print args
        if "-debug" in args:
            self._collector.b_compiled_debug = True
            sublime.set_timeout(lambda: self._collector.view.run_command("unreal_install_debugger", {"b_64bit": "Win64" == self._collector.compile_settings[0][:5]}), 0)
        # pipe = subprocess.Popen([self.exe_path, args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)
        pipe = subprocess.Popen(["cmd", args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)
        # saves output lines
        bfirst = True
        while True:
            line = pipe.stdout.readline()
            if not line:
                break
            self._collector._output.append(line.rstrip())
            if bfirst:
                bfirst = False
                sublime.set_timeout(lambda: print_to_panel(self._collector.view, line), 0)
            else:
                sublime.set_timeout(lambda: print_to_panel(self._collector.view, line, False), 0)
            time.sleep(0.002)

        output_text = "".join(self._collector._output)
        if "Warning/Error Summary" in output_text:
            if "Failure" in self._collector._output[-3]:
                print "Error"
                self._collector._b_open_output = True
            else:
                print "Warning"
                self._collector._b_ask_if_open_output = True
        else:
            print "everything's fine!"

        self.stop()

    def stop(self):
        if self.isAlive():
            self._Thread__stop()
