<#
.SYNOPSIS
  Verifica che Ollama sia raggiungibile dal PC e DA DENTRO il cluster (dove gira Superset).

.PARAMETER OllamaUrl
  Indirizzo da provare (default: la Spark sulla porta 11434).
#>
[CmdletBinding()]
param([string]$OllamaUrl = "http://10.100.208.51:11434")

$uri = [Uri]$OllamaUrl

Write-Host "==> 1. Dal PC: porta $($uri.Port) su $($uri.Host)"
$t = Test-NetConnection $uri.Host -Port $uri.Port -WarningAction SilentlyContinue
Write-Host ("   TcpTestSucceeded: " + $t.TcpTestSucceeded)

Write-Host "`n==> 2. Dal cluster Kubernetes (pod temporaneo con curl)"
& kubectl get namespace superset-ai *> $null
$ns = if ($LASTEXITCODE -eq 0) { "superset-ai" } else { "default" }
& kubectl run ollama-test -n $ns --rm -i --restart=Never --image=curlimages/curl:8.11.1 -- `
  curl -s -m 15 "$OllamaUrl/api/tags"
if ($LASTEXITCODE -eq 0) {
  Write-Host "`nOK: i pod raggiungono Ollama (sopra l'elenco dei modelli)."
} else {
  Write-Warning "I pod NON raggiungono $OllamaUrl. Vedi 'Se i pod non raggiungono la Spark' nel README."
}
