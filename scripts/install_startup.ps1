# DeskPlan 开机自启动安装脚本

$ProjectDir = Split-Path -Parent $PSScriptRoot

$Pythonw = Join-Path $ProjectDir ".venv\Scripts\pythonw.exe"
$Widget = Join-Path $ProjectDir "widget.py"

$StartupFolder = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupFolder "DeskPlan.lnk"


# 检查 pythonw.exe
if (-not (Test-Path $Pythonw)) {
    Write-Host "错误：找不到 pythonw.exe"
    Write-Host $Pythonw
    exit 1
}


# 检查 widget.py
if (-not (Test-Path $Widget)) {
    Write-Host "错误：找不到 widget.py"
    Write-Host $Widget
    exit 1
}


# 创建快捷方式
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)

$Shortcut.TargetPath = $Pythonw
$Shortcut.Arguments = "`"$Widget`""
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Description = "DeskPlan Desktop Widget"

$Shortcut.Save()


Write-Host ""
Write-Host "DeskPlan 开机自启动已安装。"
Write-Host ""
Write-Host "启动快捷方式："
Write-Host $ShortcutPath