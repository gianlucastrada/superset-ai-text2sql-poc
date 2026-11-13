<#
.SYNOPSIS
  Ferma la POC.

.PARAMETER Purge
  Cancella tutto il namespace "superset-ai": dati, dashboard create, password.
  Senza -Purge si fermano solo i pod: volume e Secret restano e il prossimo deploy riparte da li'.
#>
[CmdletBinding()]
param([switch]$Purge)

if ($Purge) {
  $answer = Read-Host "Cancello il namespace 'superset-ai' con TUTTI i dati. Scrivi 'si' per confermare"
  if ($answer -ne "si") { Write-Host "Annullato."; return }
  & kubectl delete namespace superset-ai
} else {
  & kubectl delete deployment superset postgres -n superset-ai --ignore-not-found
  Write-Host "Pod fermati. Dati e password conservati (usa -Purge per cancellare tutto)."
}
