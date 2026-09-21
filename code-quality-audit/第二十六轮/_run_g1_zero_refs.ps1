$ErrorActionPreference = "Continue"
Set-Location "C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\架构改造-H4H5"
& C:\Python311\python.exe scan_zero_refs.py check_dragged_file react_to_file_deletion follow_file react_to_file_emotionally delete_file rename_file open_file open_folder check_video_windows check_game_windows react_to_game watch_video interact_with_file interact_with_folder check_file_content check_text_content check_image_content 2>&1 | Out-Null
if (Test-Path "C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\架构改造-H4H5\_evidence\zero_refs.txt") {
  Copy-Item "C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\架构改造-H4H5\_evidence\zero_refs.txt" "C:\Users\23002\Desktop\项目文件夹\try - 副本\code-quality-audit\第二十六轮\_evidence\G1_zero_refs.txt" -Force
  Write-Output "COPIED"
} else {
  Write-Output "MISSING"
}
