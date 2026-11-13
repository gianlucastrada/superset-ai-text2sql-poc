<#
.SYNOPSIS
  Mostra la password dell'utente admin di Superset.
#>
$b64 = & kubectl get secret superset-ai-secrets -n superset-ai -o jsonpath='{.data.ADMIN_PASSWORD}'
if (-not $b64) { Write-Error "Secret non trovato: hai eseguito .\scripts\deploy.ps1 ?"; exit 1 }
Write-Host "Utente:   admin"
Write-Host ("Password: " + [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64)))
