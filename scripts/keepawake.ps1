Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
$end=(Get-Date).AddHours(14)
while((Get-Date) -lt $end){ [W.P]::SetThreadExecutionState(0x80000001) | Out-Null; Start-Sleep 30 }
