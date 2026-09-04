Option Explicit

Dim fileSystem, shell, scriptDirectory, pythonExecutable, applicationPath
Set fileSystem = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonExecutable = fileSystem.BuildPath( _
    fileSystem.GetParentFolderName(scriptDirectory), ".python\pythonw.exe")
applicationPath = fileSystem.BuildPath(scriptDirectory, "ppi_tool.py")

If Not fileSystem.FileExists(pythonExecutable) Then
    MsgBox "Pythonが見つかりません: " & pythonExecutable, vbCritical, "PPI公示業務"
    WScript.Quit 1
End If

shell.CurrentDirectory = scriptDirectory
shell.Run """" & pythonExecutable & """ """ & applicationPath & """", 0, False
