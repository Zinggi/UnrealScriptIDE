Unreal Debugger (v1.1.0.0)
http://code.google.com/p/unreal-debugger/
--------------------------------------------------------------------------

1. Description:

UnrealDebugger is a debugger IDE for the Unreal Development Kit. The UDK can be downloaded from http://www.udk.com

With UnrealDebugger you decide how much you want to pay for it. You can use it completely for free (commercial or non-commercial users) or if you think it is worth it, you can make a donation and support its development. Donations can be made from the following link:

https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=NF42C9AL5A9SW&lc=US&item_name=UnrealDebugger&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donate_SM%2egif%3aNonHosted


2. Contents:

+ readme.txt
+ DebuggerInterface.dll
+ UnrealDebugger.dll
+ Aga.Controls.dll
+ ICSharpCode.TextEditor.dll
+ WeifenLuo.WinFormsUI.Docking.dll



3. Installation:

Just copy UnrealDebugger files to the folder where you have the UDK.exe file. This file is usually located in the folder %UDK_PATH%\Binaries\Win32 for the 32 bit version of the UDK and %UDK_PATH%\Binaries\Win64 for the 64 bit version.

If you have already installed a debugger for the UDK (such as nFringe), you should make a backup copy of DebuggerInterface.dll before replacing it with the one provided with UnrealDebugger



4. Using the debugger:

- Before using the debugger you have to compile unreal script files with debug information using the command:

    udk.exe make -full -debug

- After compiling the scripts you can use UnrealDebugger just by launching your UDK game with the -autodebug switch. Alternatively, you can simply launch your UDK game and connect the debugger later by using the console command 'toggledebugger'

- The first time you use UnrealDebugger you may need to configure the path where your script files are located. After launching the debugger, go to the Configuration Panel and set the Project Path property to the path where your script files are located. Usually, they are in the folder %UDK_PATH%\Development\Src



Copyright (c) 2011 Carlos Lopez Menendez (email: carloslopezmdez@gmail.com)