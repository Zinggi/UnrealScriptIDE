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
import os


# Builds your udk project and gets the output.
class UnrealBuildProjectCommand(sublime_plugin.TextCommand):
    udk_exe_path = ""
    udkLift_exe_path = ""
    # the building output
    _output = []
    # there were some errors
    _b_open_output = False
    # there were just warnings
    _b_ask_if_open_output = False

    _last_opened_map = ""
    _selected_map = ""

    b_build_and_run = False

    _b_Multi_Player = False
    # a list of additional startup settings.
    additional_startup_settings = ""

    # find src folder and start building
    def run(self, edit, b_build_and_run=False):
        if self.view.file_name() is not None:   # and is_unrealscript_file(self.view.file_name()):
            self.settings = sublime.load_settings('UnrealScriptIDE.sublime-settings')
            possible_src_folders = []
            open_folder_arr = self.view.window().folders()   # Gets all opened folders in the Sublime Text editor.
            self.b_build_and_run = b_build_and_run

            # search open folders for Src directory
            for folder in open_folder_arr:
                if "Src" in folder:
                    possible_src_folders.append(folder)
                else:
                    possible_src_folders.append(self.search_src_in(folder))
            # get the right one!
            for folder in possible_src_folders:
                if not folder:
                    continue
                if "\Development\Src" in folder:
                    self.udk_exe_path = folder

            # Removing "Development\Src" and adding the UDK.com path (this is probably not how it's done correctly):
            self.udk_exe_path = self.udk_exe_path[:-15] + "Binaries\\Win32\\UDK.com"
            self.udkLift_exe_path = self.udk_exe_path[:-13] + "UDKLift.exe"
            self.udk_maps_folder = self.udk_exe_path[:-22] + "UDKGame\\Content\\Maps"
            self.start_build()

    # starts building your game. This adds a new UDKbuild thread.
    def start_build(self):
        self._output = []
        self._build_thread = UDKbuild(self.udk_exe_path, self)
        self._build_thread.start()
        self.handle_thread()

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
            elif self._b_ask_if_open_output:
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
                                "'Preferences' -> 'Package Settings' -> 'UnrealScriptIDE' -> 'Settings - User'"],

                                ["Always open game. Never ask for log again!",
                                "You can reset your choice under:",
                                "'Preferences' -> 'Package Settings' -> 'UnrealScriptIDE' -> 'Settings - User'"]]
                self.view.window().show_quick_panel(input_list, self.on_done_warnings_input)

                self._b_ask_if_open_output = False

            # == no warnings and no errors, start the game.
            else:
                self.run_game()

    # shows the building error log, with summery at the top
    def show_error_panel(self):
        log_cache = os.path.join(sublime.packages_path(), "UnrealScriptIDE\\log_cache.log")
        with open(log_cache, 'w') as log:
            log_massage = "==============\nBUILD RESULTS:\n==============\n\nNote:\nuse UnrealScript Goto Definition to navigate to errors. (by default with f10, alt + LMB, context menu or via 'Goto' -> 'UnrealScript Goto Declaration')\n----------------------------------------------\n\n"
            log_massage += self.get_summery()
            log_massage += "\n\n\n\n\n\n\n\n\n\n\n----------------------------------------------\nFull log:\n----------------------------------------------\n\n\n"
            log_massage += "\n".join(self._output)
            log.write(log_massage)

        sublime.active_window().open_file(log_cache)
        sublime.active_window().open_file(log_cache)

    # gets called from the warning input panel
    def on_done_warnings_input(self, index):
        # 0 = open log, 1 = run game, 2 = always log, 3 = always run game, -1 = was canceled
        if index == 0:
            self.show_error_panel()
        elif index == 1:
            self.run_game()
        elif index == 2:
            self.settings.set('always_open_log', True)
            sublime.save_settings('UnrealScriptIDE.sublime-settings')
            self.show_error_panel()

        elif index == 3:
            self.settings.set('always_start_game', True)
            sublime.save_settings('UnrealScriptIDE.sublime-settings')
            self.run_game()
        elif index == -1:
            pass
        else:
            print "unhandled case!!!"

    # Ask the user to enter a start map to start the game.
    # ask if wants to open server + two clients
    def run_game(self):
        if self._last_opened_map == "":
            self._last_opened_map = self.settings.get('last_opened_map')
        self._b_Multi_Player = self.settings.get('b_multi_player')

        if self.b_build_and_run:
            self.on_done_run_game_input(0)
            return

        input_list = [["Start with last opened map",
                        self._last_opened_map + (", Server and 2 Clients" if self._b_Multi_Player else ", Standalone")],
                        "Start with default map"]
        # add all maps found in the maps folder.
        self._map_list = self.search_mapfiles(self.udk_maps_folder)
        if not self._map_list:
            return
        input_list += self._map_list

        self.view.window().show_quick_panel(input_list, self.on_done_run_game_input)

    # gets called from the run game input. Opens the chosen map.
    def on_done_run_game_input(self, index):
        self.additional_startup_settings = self.settings.get('additional_startup_settings')
        # 0 = open last map, 1 = open default, else: open map index, -1 = was canceled
        if index == 0:
            if self._b_Multi_Player:
                # open server and 2 clients
                subprocess.Popen([self.udkLift_exe_path, "server " + self._last_opened_map + self.settings.get('additional_startup_settings_server')])
                subprocess.Popen([self.udkLift_exe_path, "127.0.0.1 " + self.settings.get('additional_startup_settings_client1')])
                subprocess.Popen([self.udkLift_exe_path, "127.0.0.1 " + self.settings.get('additional_startup_settings_client2')])
            else:
                subprocess.Popen([self.udkLift_exe_path, self._last_opened_map + self.additional_startup_settings])
        elif index == 1:
            subprocess.Popen([self.udkLift_exe_path, self.additional_startup_settings])
        elif index == -1:
            pass
        else:
            self._selected_map = self._map_list[index - 2][0]

            input_list = [["Start Standalone game",
                        "Your choice will be remembered, next time you can use:",
                        "'Start with last opened map'"],
                        ["Start a Server and connect 2 Clients",
                        "Your choice will be remembered, next time you can use:",
                        "'Start with last opened map'"]]

            self.view.window().show_quick_panel(input_list, self.on_done_single_or_multi)

    def on_done_single_or_multi(self, index):
        # 0 = single-player, 1 = multi-player, -1 = back to run game dialog
        if index == 0:
            self._last_opened_map = self._selected_map
            self.settings.set('last_opened_map', self._last_opened_map)

            self._b_Multi_Player = False
            self.settings.set('b_multi_player', self._b_Multi_Player)

            sublime.save_settings('UnrealScriptIDE.sublime-settings')

            subprocess.Popen([self.udkLift_exe_path, self._last_opened_map + self.additional_startup_settings])
        elif index == 1:
            self._last_opened_map = self._selected_map
            self.settings.set('last_opened_map', self._last_opened_map)

            self._b_Multi_Player = True
            self.settings.set('b_multi_player', self._b_Multi_Player)

            sublime.save_settings('UnrealScriptIDE.sublime-settings')
            # open server and 2 clients
            subprocess.Popen([self.udkLift_exe_path, "server " + self._last_opened_map + self.settings.get('additional_startup_settings_server')])
            subprocess.Popen([self.udkLift_exe_path, "127.0.0.1 " + self.settings.get('additional_startup_settings_client1')])
            subprocess.Popen([self.udkLift_exe_path, "127.0.0.1 " + self.settings.get('additional_startup_settings_client2')])

        elif index == -1:
            self.run_game()
        else:
            print "unhandled case!!!"

    # returns all map files in the path folder
    def search_mapfiles(self, path):
        maps = []
        if not os.path.exists(path):
            print "maps not found"
            return
        for file in os.listdir(path):
            dirfile = os.path.join(path, file)

            if os.path.isdir(dirfile):
                maps += self.search_mapfiles(dirfile)
            elif ".udk" in dirfile:
                maps.append([file, dirfile])

        return maps

    # search for the Src folder in the path. Returns the found folder.
    def search_src_in(self, path):
        for file in os.listdir(path):
            dirfile = os.path.join(path, file)

            if os.path.isdir(dirfile):
                if "Src" in dirfile:
                    return dirfile
                else:
                    return self.search_src_in(dirfile)

    # returns the found summery in a building log file.
    def get_summery(self):
        i = self._output.index("Warning/Error Summary")
        return "\n".join(self._output[i:])


# Builds your project and captures the building log output
class UDKbuild(threading.Thread):
    _collector = None

    def __init__(self, exe_path, collector):
        self.exe_path = exe_path
        self._collector = collector
        threading.Thread.__init__(self)

    def run(self):  # gets called when the thread is created
        if not os.path.exists(self.exe_path):
            print "UDK.exe not found!!!"
            self.stop()
            return
        pipe = subprocess.Popen([self.exe_path, "make"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # saves output lines
        while True:
            line = pipe.stdout.readline()
            if not line:
                break
            self._collector._output.append(line.rstrip())

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


def is_unrealscript_file(filename):
    return '.uc' in filename
