$ProgressPreference = 'SilentlyContinue'
$outPath = "$env:TEMP\blender-5.2.1-windows-x64.msi"
Write-Host "Downloading Blender 5.2.1 LTS to $outPath ..."
Invoke-WebRequest -Uri "https://download.blender.org/release/Blender5.2/blender-5.2.1-windows-x64.msi" -OutFile $outPath -UseBasicParsing
$size = [math]::Round((Get-Item $outPath).Length / 1MB, 1)
Write-Host "Download complete! Size: $size MB"
Write-Host "Path: $outPath"
