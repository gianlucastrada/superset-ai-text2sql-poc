<#
.SYNOPSIS
  Port-forward di Superset su http://localhost:8088 (Ctrl+C per chiudere).
#>
Write-Host "Apri http://localhost:8088  (utente admin, password: .\scripts\password.ps1)"
Write-Host "Ctrl+C per fermare."
& kubectl port-forward -n superset-ai svc/superset 8088:8088
