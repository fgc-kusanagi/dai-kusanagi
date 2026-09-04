Option Explicit

Dim fileSystem, shell, scriptDirectory, pythonExecutable, applicationPath
Set fileSystem = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonExecutable = fileSystem.BuildPath(fileSystem.GetParentFolderName(scriptDirectory), ".python\pythonw.exe")
applicationPath = fileSystem.BuildPath(scriptDirectory, "ppi_tool.py")

If Not fileSystem.FileExists(pythonExecutable) Then
    MsgBox "Python was not found: " & pythonExecutable, vbCritical, "PPI Web Launcher"
    WScript.Quit 1
End If

If WScript.Arguments.Named.Exists("check") Then
    WScript.Quit 0
End If

shell.CurrentDirectory = scriptDirectory
shell.Run """" & pythonExecutable & """ """ & applicationPath & """", 0, False
