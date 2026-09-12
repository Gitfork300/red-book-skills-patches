Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32Focus {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
}
"@

$procs = Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }
$count = 0
foreach ($p in $procs) {
    $h = $p.MainWindowHandle
    if ([Win32Focus]::IsIconic($h)) {
        [Win32Focus]::ShowWindow($h, 9)   # SW_RESTORE
    } else {
        [Win32Focus]::ShowWindow($h, 3)   # SW_MAXIMIZE
    }
    [Win32Focus]::SetForegroundWindow($h)
    $count++
}
Write-Output "activated_windows=$count"
