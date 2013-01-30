#UnrealScript IDE Plug-in for Sublime Text 2
* * *

UnrealScript IDE mainly adds better auto-completion features to Sublime Text 2 for UnrealScript and a goto declaration command.


![Pic](http://www.mediafire.com/conv/a12c7703e035e63ecb6ff1d39b8677716286a0f50c386ac5de0329f53e3e1e3d6g.jpg)


Feautures
------------

* **dynamic, intelligent auto-completion**
	* parameter hints
	* display documentation when you need it
	* completions feel like the great Sublime Text 2 snippets
	* get other completions depending where you are typing (e.g. in the defaultproperties block you only want to get variables)

* **goto declaration and back again** (F10, alt + left, right click menu or via 'Goto' -> 'UnrealScript Goto Declaration')

* **Add bookmarks to your comments** and navigate to them quickly via Ctrl + R (just write your comments like this: // ! text or /** ! text*/)

* **more coming...**


Planned
------------

* **object-oriented auto-completions**
	* if you write e.g. "Controller." you'd want to see it's methods, functions and variables. Currently this doesn't work.
* **add support for enumerations, structs and CONST**
* **multiline function declaration aren't parsed right yet**


Installation
------------

**Very easy with [Package Control](http://wbond.net/sublime_packages/package_control "http://wbond.net/sublime_packages/package_control") right inside Sublime Text 2 (Package Control needs to be installed):**

1.	Ctrl + shift + P
2.  Search for "inst", hit enter
3.  Search for "UnrealScriptIDE", hit enter

**Manually (the idiotically tedious way ;-) ):**

1.  Clone or download this package
2.	Put it into your Packages directory (find using 'Preferences' -> 'Browse Packages...')

**please note:**
UnrealScriptIDE will only work properly if you add the src folder as a project. 
To do so, goto 'Project' -> 'Add Folder To Project...' -> add the Src folder (/UDK/UDK-201*-**/Development/Src/)

------------
*For syntax highlighting, various snippets and integrated build system I'd recommend downloading the package "UnrealScript"
by Michael Alexander with "Package Control" or manually from [here](https://github.com/beefsack/unrealscript-sublime "https://github.com/beefsack/unrealscript-sublime") to truly make this an UnrealScript IDE*

My auto-complete settings
------------
Here are some relevant settings for auto-completion that I've found quite helpful:

	{
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