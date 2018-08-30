UnrealScript IDE Plug-in for Sublime Text 2/3
===========================

UnrealScript IDE adds many features to Sublime Text 2/3 that you'd expect from a good UnrealScript IDE.  
Fully featured object-oriented auto-completion, go to declaration, syntax highlighting, build and run, snippets and some more to name a few...


![Pic](https://lh3.googleusercontent.com/61K4WHO5xEbq9qKU2v2tWjVmmk7Ot0SutLj6t2aTjAQgccv86a24ooZjp7QZ2AAltxXZrda6UqUlBP4zMQysr7E1OES-Hl5jafnkeBGa--7kK52AzoiMkstvIKb6Pes0hzMl6EyZwhzPbEm2P8ok5QSHtUbREa9HSblw09SzhRuMWjy2RpkgKY61MdClzDiziMmYS_hZG22G60DO05xesYB7dfcTfF0dpbsV5h43Ruwgk9UBv8PNmuNsBsvRSsTsyl32ca0Fm9HI6p5Mogfln8bhlrFEQY8gBG6cEayStHmLHUckwuMFqtmzp_21xIfXngJd26Uoj5ee40fTquBiu9qQDe7RwogC3smazuxf6OmCE4wWa_4z96o6EoJzhH7mzzJM9hoO_YVgCvWjnzk6DPGqmv65dCO9vYCVe7duCJOArJKHoF6rYWGEkmMWhKprNe34tL65YThG6PWdtz5c5xB886P99FiAwViu5kCtOHFLi2YIWKHLtvwBc2LmomweSHbp_UBA28tb9cN6-4gqWEhNGW66vcK_6x2IgvTI0vP7_-CELRqVWwRO5pQ924aziXyX1P17fXabLxR9UTawO-zJ2l3Yks8b_LpqFnd0lx3pQMP-CPvb4w6gL06uiyb-B3Y62HBPsKabSXlC6qzoA98609aPOZs2iaXbgsbR3_7oqiADShg8f6y3Lg=w640-h390-no)


Features
------------

* **Dynamic, intelligent auto-completions**
	* fully object-oriented completions
	* context sensitive completions (e.g. in the defaultproperties block you only want to get variables)
	* content assist. You wont have to open the editor anymore to search for asset names.
	* parameter hints
	* display documentation when you need it
	* completions feel like the great Sublime Text 2/3 snippets

* **Go to declaration and back again**
	* object-oriented go to declaration (pressing it over controller.GetPlayerViewPoint(a, b) will take you to the declaration of GetPlayerViewPoint in Controller)
	* go to the declaration of the currently selected word via F10, alt + left click, right click menu, 'Goto' -> 'UnrealScript Goto Declaration' or search for it in in the command palette 
	* when browsing in the declarations you can always return to your starting position by using one of the above keys when nothing is under your cursor.

* **Debugger**
	* UnrealScript IDE comes with [UnrealDebugger](https://code.google.com/p/unreal-debugger/) integrated.
	* You can set breakpoints directly inside Sublime Text 2/3
	* [more information](https://github.com/Zinggi/UnrealScriptIDE/wiki/Usage#debugger)

* **Syntax highlighting**
	* For .uc files and .log files

* **Build system**
	* to build your game use Ctrl + B, F7 or search for it in the command palette.
	* if the build contains errors, the error log will be opened, allowing you to navigate to your errors quickly.
	* if the build was successful, the game will start

* **Launch Game**
	* quickly open the game with your last configuration
	* you can chose which map to open
	* chose between Standalone or a Server and 2 Clients or add any other configuration you might like
	* [more information](https://github.com/Zinggi/UnrealScriptIDE/wiki/Usage#launch-game)

* **Various useful Snippets**
	* predefined Snippets for standard classes, and language features such as defaultproperties

* **Add bookmarks to your comments**
	* to add a bookmark write your comments like this: // ! text or /** ! text*/
	* navigate to them quickly via Ctrl + R

* **More coming...**


Planned
------------

* **Add support for enumerations**

* **Your suggestion here?**
	* You can suggest features, report bugs and vote for features on this site here: [UnrealScript IDE - Userecho](http://unrealscriptide.userecho.com/)


Installation
------------
**Very easy with [Package Control](http://wbond.net/sublime_packages/package_control) right inside Sublime Text 2/3 (Package Control needs to be installed):**

1.	Ctrl + shift + P
2.  Search for "install", hit enter
3.  Search for "UnrealScriptIDE", hit enter

For a more in detail explanation visit the wiki: https://github.com/Zinggi/UnrealScriptIDE/wiki/Getting-Started

**Manually (not recommended):**

1.  Clone or download this package
2.	Put it into your Packages directory (find using 'Preferences' -> 'Browse Packages...')

**please note:**
----------------
UnrealScriptIDE will **only** work properly if you add the **Src** folder as a project.  
To do so, goto 'Project' -> 'Add Folder To Project...' -> add the Src folder (/UDK/UDK-201*-**/Development/Src/)

Usage
----------------
Please refer to the wiki: https://github.com/Zinggi/UnrealScriptIDE/wiki

------------
All **credits** for [UnrealDebugger](https://code.google.com/p/unreal-debugger/) goes to **[Carlos Lopez](https://code.google.com/u/105243014413414365723/)**. Huge Thanks!  
All **credits** for various Snippets (and also for the old (now unused) Syntax highlighting file) goes to **[Michael Alexander](https://github.com/beefsack)**. Thanks!  
All **credits** for Syntax highlighting in UnrealScript files goes to **[Rokit](https://github.com/rokit)** and **[Eliot](https://github.com/EliotVU)**. Thanks!  
**Credits** for Syntax highlighting in Log files goes to **[Rokit](https://github.com/rokit)**. Thanks!

If UnrealScriptIDE is helpfull to you, please consider making a donation. (Especially when you're using it commercially)  
[![Donate](https://www.paypalobjects.com/en_GB/i/btn/btn_donate_SM.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=XT5LYESK99ESA)
[![gittip](http://i.imgur.com/lg9rx9w.png)](https://www.gittip.com/Zinggi/)  **Thanks!**

My auto-complete settings
------------
Here are some relevant settings for auto-completion that I've found quite helpful:

	{
		"auto_complete_with_fields": true,	//this allows auto-completion inside snippets.
		"auto_complete_triggers":	//this activates auto-completion on '.'
		[
			{
				"characters": ".",
				"selector": "source.unrealscript"
			}
		],
		"auto_complete_delay": 0,
		"auto_complete_commit_on_tab": true,	// I prefer 'tab' to 'enter'
	}


* * *
License
------------
UnrealScript IDE Plug-in for Sublime Text 2/3
Copyright (C) 2013 Florian Zinggeler

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
