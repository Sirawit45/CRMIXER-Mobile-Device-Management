import os
import subprocess

desktop = os.path.join(os.path.expanduser("~"), "Desktop")
shortcut_path = os.path.join(desktop, "CRMIXER MDM.lnk")
target = r"C:\Users\Jo_save\Desktop\Mobile manag\run.bat"
work_dir = r"C:\Users\Jo_save\Desktop\Mobile manag"
icon = r"C:\Users\Jo_save\Desktop\Mobile manag\bin\scrcpy\scrcpy.exe"

ps_cmd = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
$Shortcut.TargetPath = '{target}'
$Shortcut.WorkingDirectory = '{work_dir}'
$Shortcut.IconLocation = '{icon},0'
$Shortcut.Save()
'''

with open("create_shortcut.ps1", "w", encoding="utf-8") as f:
    f.write(ps_cmd)

subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", "create_shortcut.ps1"])
if os.path.exists("create_shortcut.ps1"):
    os.remove("create_shortcut.ps1")

print("Created shortcut on Desktop at:", shortcut_path)
