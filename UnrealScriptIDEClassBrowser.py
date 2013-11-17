#-----------------------------------------------------------------------------------
# UnrealScriptIDE experimental class-browser
#-----------------------------------------------------------------------------------
#
#
#
# (c) Florian Zinggeler
#-----------------------------------------------------------------------------------
import sublime
import sublime_plugin

ST3 = int(sublime.version()) > 3000
if ST3:
    import UnrealScriptIDE.UnrealScriptIDEMain as USMain
    from UnrealScriptIDE.UnrealBuildSystem import show_quick_panel
else:
    import UnrealScriptIDEMain as USMain
    from UnrealBuildSystem import show_quick_panel


class UnrealClassBrowserCommand(sublime_plugin.TextCommand):
    selected_file = None
    history = []
    b_expand = False

    def run(self, edit):
        # Object
        # --open file--
        # --show members--
        #   Actor
        USMain.evt_m().parsing_finished += self.on_parsing_finished
        USMain.evt_m().get_class_reference(self.receive_object)
        self.show_tree()

    def show_tree(self, b_expand=False):
        self.b_expand = b_expand
        self.input_list = [[("Back to " + self.selected_file.parent_class()) if self.selected_file.parent_class() != "" else "Close"],
                           ["Open file: " + self.selected_file.name(),
                            self.selected_file.file_name()]]

        if not b_expand:
            self.input_list += [["v Expand Members v",
                                 "expand and show all functions and variables. (Might take a moment)"]]
        else:
            self.input_list += [["^ Collapse Members ^",
                                 "Hide all members of this class"]]
            if self.selected_file.has_parsed():
                for v in self.selected_file.get_variables():
                    self.input_list += [["|_ " + v.name(),
                                         v.declaration()]]
                for f in self.selected_file.get_functions():
                    self.input_list += [["|_ " + f.function_name(),
                                         v.declaration()]]
            else:
                self.input_list += [["Just a moment...",
                                     "Class needs to be parsed first..."]]
                self.selected_file.parse_me()

        for c in self.selected_file.children():
            self.input_list.append(["    " + c.name()])

        # self.view.window().
        show_quick_panel(self.input_list, self.on_click)

    def receive_object(self, obj):
        self.object = obj
        self.selected_file = self.object

    def on_click(self, index):
        if index == -1 or index == 0:
            if len(self.history) >= 1:
                self.selected_file = self.history.pop()
                self.show_tree(self.b_expand)
            else:
                USMain.evt_m().parsing_finished -= self.on_parsing_finished
        elif index == 1:
            print("open")
        elif index == 2:
            self.show_tree(not self.b_expand)
        else:
            self.history.append(self.selected_file)
            comp = self.selected_file.get_variables() + self.selected_file.get_functions()
            if self.input_list[index - 3][0][0] == "|":
                self.view.window().run_command("unreal_goto_definition", {"b_new_start_point": True, "line_number": comp[index - 3].line_number(), "filename": comp[index - 3].file_name()})
            else:
                self.selected_file = self.selected_file.children()[index - 3 - (len(comp) if self.b_expand else 0)]
                self.show_tree(self.b_expand)

    def on_parsing_finished(self):
        self.view.window().run_command("hide_overlay")
        self.show_tree(self.b_expand)
