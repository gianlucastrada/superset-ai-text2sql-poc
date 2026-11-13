<#
.SYNOPSIS
  Aggiorna le viste di analisi (postgres\init\05-viste-vendite.sql) sul Postgres gia' in
  esecuzione, senza perdere dati e dashboard. Poi riavvia Superset per rileggere lo schema.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Ns = "superset-ai"
$file = Join-Path $Root "postgres\init\05-viste-vendite.sql"

Write-Host "==> Applico $file"
$sql = Get-Content $file -Raw
$sql | & kubectl exec -i -n $Ns deploy/postgres -- psql -U postgres -d vendite -v ON_ERROR_STOP=1
if ($LASTEXITCODE -ne 0) { throw "Aggiornamento del database fallito." }

Write-Host "`n==> Verifica"
& kubectl exec -n $Ns deploy/postgres -- psql -U postgres -d vendite -At -c "SELECT 'v_vendite (senza annullati): ' || round(sum(importo)) FROM v_vendite UNION ALL SELECT 'v_vendite_tutte (con annullati): ' || round(sum(importo)) FROM v_vendite_tutte UNION ALL SELECT 'v_ordini (ordini annullati, atteso 290): ' || count(*) FROM v_ordini WHERE stato = 'Annullato'"

Write-Host "`n==> Riavvio Superset (rilegge lo schema per l'IA)"
& kubectl rollout restart deployment/superset -n $Ns
& kubectl rollout status deployment/superset -n $Ns --timeout=600s
Write-Host "Fatto."
