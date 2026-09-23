# DeskPlan 开机自启动卸载脚本

$StartupFolder = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupFolder "DeskPlan.lnk"


if (Test-Path $ShortcutPath) {

    Remove-Item $ShortcutPath

    Write-Host ""
    Write-Host "DeskPlan 开机自启动已关闭。"

}
else {

    Write-Host ""
    Write-Host "没有找到 DeskPlan 的开机启动项。"
}