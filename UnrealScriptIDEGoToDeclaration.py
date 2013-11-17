#-----------------------------------------------------------------------------------
# UnrealScriptIDE Go to Declaration
#-----------------------------------------------------------------------------------
#
#   Adds the go to declaration command.
#   This will take you to the declaration of the word located under your courser.
#   In log files this will take you to the corresponding line.
#
# (c) Florian Zinggeler
#-----------------------------------------------------------------------------------
import sublime
import sublime_plugin
import re
import os

ST3 = int(sublime.version()) > 3000
if ST3:
    import UnrealScriptIDE.UnrealScriptIDEMain as USMain
else:
    import UnrealScriptIDEMain as USMain

last_location = None
current_location = None


def is_unreal_log_file():
    window = sublime.active_window()
    if window:
        view = window.active_view()
        if view:
            return "UnrealScriptIDE/Log.tmLanguage" in view.settings().get('syntax')
    return False


####################################################
# Go to Declaration
# -----------------
#
# TODO:
#   - Add a navigation history for better navigation.
#   - (erase status 'not found') ??? don't remember what that was about...
####################################################

# opens the definition of the current selected word.
#  - if b_new_start_point is true, the current cursor position will be stored as a return point.
class UnrealGotoDefinitionCommand(sublime_plugin.TextCommand):
    def run(self, edit, b_new_start_point=False, line_number=-1, filename=""):
        if USMain.is_unrealscript_file():
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
                left_line = USMain.get_relevant_text(line)
                # print left_line

            # calculate where to go inside the main instance of my plug-in.
            # Then, call this command again with a filename and a line number.
            USMain.evt_m().go_to_definition(left_line, word, line, b_new_start_point)

        elif is_unreal_log_file():  # self.view.file_name()
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
            settings = sublime.load_settings('UnrealScriptIDE.sublime-settings')
            new_w = settings.get('b_create_new_window_goto_def')

            flags = sublime.ENCODED_POSITION if new_w else (sublime.ENCODED_POSITION | sublime.TRANSIENT)
            # somehow calling this twice fixes a bug that makes sublime crash, no idea why though...
            window.open_file(file_name + ':' + str(line_number) + ':0', flags)
            window.open_file(file_name + ':' + str(line_number) + ':0', flags)
            current_location = file_name
        else:
            self.view.set_status('UnrealScriptGotoDefinition', '"' + file_name + '" does not exist!')
