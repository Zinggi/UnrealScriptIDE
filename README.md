UnrealScript IDE Plug-in for Sublime Text 2
===========================

UnrealScript IDE mainly adds better auto-completion features to Sublime Text 2 for UnrealScript and a goto declaration command.


![Pic](http://www.mediafire.com/conv/a12c7703e035e63ecb6ff1d39b8677716286a0f50c386ac5de0329f53e3e1e3d6g.jpg)


Feautures
------------

* **Dynamic, intelligent auto-completion**
	* parameter hints
	* display documentation when you need it
	* completions feel like the great Sublime Text 2 snippets
	* get other completions depending where you are typing (e.g. in the defaultproperties block you only want to get variables)

* **Go to declaration and back again**
	* use F10, alt + left click, right click menu, via 'Goto' -> 'UnrealScript Goto Declaration' or search in the command palette to go to the declaration of the currently selected word
	* when browsing in the declarations you can always return to your starting position by using one of the above keys when nothing is under your cursor.
	* Object-oriented goto declaration (pressing it over controller.GetPlayerViewPoint(a, b) will take you to the declaration of GetPlayerViewPoint in Controller)

* **Syntax highlighting**

* **Build system**
	* use Ctrl + B, F7 or search in the command palette to build your game
	* if the build contains errors, the error log will be opened, allowing you to navigate to your errors quickly.
	* if the build was successful, the game will start

* **Launch Game**
	* quickly open the game with your last configuration
	* you can chose witch map to open
	* chose between Standalone or a Server and 2 Clients
	* you can specify additional startup settings

* **Various useful Snippets**

* **Add bookmarks to your comments**
	* to add a bookmark write your comments like this: // ! text or /** ! text*/
	* navigate to them quickly via Ctrl + R

* **More coming...**


Planned
------------

* **Object-oriented auto-completions**
	* if you write e.g. "Controller." you'd want to see it's methods, functions and variables. Currently this doesn't work.

* **Object-oriented goto declaration command**
	* typecasting e.g. Actor(Pawn). and super(className). are not supported yet

* **Add support for enumerations, structs and CONST**

* **Your suggestion here?**
	* You can suggest features, report bugs and vote for features on this site here: [UnrealScript IDE - Userecho](http://unrealscriptide.userecho.com/)


Installation
------------
**Very easy with [Package Control](http://wbond.net/sublime_packages/package_control) right inside Sublime Text 2 (Package Control needs to be installed):**

1.	Ctrl + shift + P
2.  Search for "inst", hit enter
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
All **credits** for various Snippets (and also for the old (now unused) Syntax highlighting file) goes to **[Michael Alexander](https://github.com/beefsack)**. Thanks!
All **credits** for Syntax highlighting in UnrealScript files goes to **[Rokit](https://github.com/rokit)** and **[Eliot](https://github.com/EliotVU)**. Thanks!
**Credits** for Syntax highlighting in Log files goes to **[Rokit](https://github.com/rokit)**. Thanks!

My auto-complete settings
------------
Here are some relevant settings for auto-completion that I've found quite helpful:

	{
		"auto_complete_with_fields": true,	//this allows auto-completion inside snippets.
		"auto_complete_triggers":	//this activates auto-completion on '.' and '('
		[
			{
				"characters": ".(",
				"selector": "source.unrealscript"
			}
		],
		"auto_complete_delay": 0,
		"auto_complete_commit_on_tab": true,	// I prefer 'tab' to 'enter'
	}


* * *
License
------------
UnrealScript Auto-complete Plug-in for Sublime Text 2
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