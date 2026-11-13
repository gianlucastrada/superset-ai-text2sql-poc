<#
.SYNOPSIS
  Costruisce l'immagine Superset con l'estensione AI e distribuisce Postgres + Superset
  nel namespace "superset-ai" del Kubernetes di Docker Desktop.

.PARAMETER OllamaUrl
  Indirizzo di Ollama raggiungibile DAI POD (default: la Spark, porta 11434).

.PARAMETER Model
  Modello Ollama da usare (default: qwen3.6:35b).

.PARAMETER SkipBuild
  Non ricostruisce l'immagine (usa quella gia' presente).

.PARAMETER Forward
  Alla fine avvia il port-forward su http://localhost:8088

.EXAMPLE
  .\scripts\deploy.ps1
  .\scripts\deploy.ps1 -Forward
  .\scripts\deploy.ps1 -OllamaUrl http://host.docker.internal:11435
#>
[CmdletBinding()]
param(
  [string]$OllamaUrl = "http://10.100.208.51:11434",
  [string]$Model = "qwen3.6:35b",
  [switch]$SkipBuild,
  [switch]$Forward
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Ns = "superset-ai"
$Image = "superset-ai:0.1"

function Invoke-Native {
  param([string]$Exe, [string[]]$Arguments)
  & $Exe @Arguments
  if ($LASTEXITCODE -ne 0) { throw "'$Exe $($Arguments -join ' ')' e' fallito (exit code $LASTEXITCODE)." }
}

function Test-Kube {
  # True se il comando kubectl riesce; silenzioso e senza eccezioni (PowerShell 5.1)
  param([string[]]$Arguments)
  $old = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try { & kubectl @Arguments 2>$null | Out-Null; return ($LASTEXITCODE -eq 0) }
  finally { $ErrorActionPreference = $old }
}

function Apply-Yaml {
  # Applica YAML generato con --dry-run=client (ConfigMap da file o letterali)
  param([string[]]$CreateArgs)
  $yaml = & kubectl @CreateArgs --dry-run=client -o yaml
  if ($LASTEXITCODE -ne 0) { throw "Generazione YAML fallita: kubectl $($CreateArgs -join ' ')" }
  $yaml | & kubectl apply -f -
  if ($LASTEXITCODE -ne 0) { throw "kubectl apply fallito per: $($CreateArgs -join ' ')" }
}

function New-Secret([int]$Length) {
  $chars = [char[]]'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
  $bytes = New-Object byte[] $Length
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($bytes)
  $rng.Dispose()
  return -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })
}

foreach ($c in @("docker", "kubectl")) {
  if (-not (Get-Command $c -ErrorAction SilentlyContinue)) { throw "Comando '$c' non trovato nel PATH." }
}
$ctx = (& kubectl config current-context) 2>$null
Write-Host "Contesto kubectl: $ctx"
if ($ctx -ne "docker-desktop") {
  Write-Warning "Il contesto non e' 'docker-desktop': l'immagine locale potrebbe non essere visibile al cluster."
}

# 1. Immagine Superset
if (-not $SkipBuild) {
  Write-Host "`n==> docker build $Image (la prima volta scarica apache/superset:6.1.0, circa 1-2 GB)"
  Invoke-Native docker @("build", "-t", $Image, (Join-Path $Root "superset"))
}

# 2. Namespace
Write-Host "`n==> Namespace $Ns"
Invoke-Native kubectl @("apply", "-f", (Join-Path $Root "k8s\00-namespace.yaml"))

# 3. Secret con le password (creato una sola volta: Postgres le usa solo alla prima inizializzazione)
$adminPassword = $null
if (Test-Kube @("get", "secret", "superset-ai-secrets", "-n", $Ns)) {
  Write-Host "Secret gia' presente: password invariate."
} else {
  Write-Host "`n==> Creo il Secret con password casuali"
  $adminPassword = New-Secret 16
  Invoke-Native kubectl @("create", "secret", "generic", "superset-ai-secrets", "-n", $Ns,
    "--from-literal=POSTGRES_PASSWORD=$(New-Secret 24)",
    "--from-literal=SUPERSET_DB_PASSWORD=$(New-Secret 24)",
    "--from-literal=AI_READER_PASSWORD=$(New-Secret 24)",
    "--from-literal=SUPERSET_SECRET_KEY=$(New-Secret 48)",
    "--from-literal=ADMIN_PASSWORD=$adminPassword")
}

# 4. ConfigMap: script di inizializzazione Postgres e impostazioni di Ollama
Write-Host "`n==> ConfigMap"
Apply-Yaml @("create", "configmap", "postgres-init", "-n", $Ns, "--from-file=$(Join-Path $Root 'postgres\init')")
Apply-Yaml @("create", "configmap", "superset-ai-config", "-n", $Ns,
  "--from-literal=OLLAMA_URL=$OllamaUrl", "--from-literal=OLLAMA_MODEL=$Model")

# 5. Postgres
Write-Host "`n==> Postgres"
Invoke-Native kubectl @("apply", "-f", (Join-Path $Root "k8s\10-postgres.yaml"))
Invoke-Native kubectl @("rollout", "status", "deployment/postgres", "-n", $Ns, "--timeout=300s")

# 6. Superset
Write-Host "`n==> Superset"
$alreadyDeployed = Test-Kube @("get", "deployment/superset", "-n", $Ns)
Invoke-Native kubectl @("apply", "-f", (Join-Path $Root "k8s\20-superset.yaml"))
if ($alreadyDeployed) {
  # Immagine ricostruita con lo stesso tag o impostazioni Ollama cambiate: serve un pod nuovo
  Invoke-Native kubectl @("rollout", "restart", "deployment/superset", "-n", $Ns)
}
Write-Host "Attendo Superset (il primo avvio con inizializzazione puo' richiedere alcuni minuti)..."
& kubectl rollout status deployment/superset -n $Ns --timeout=900s
if ($LASTEXITCODE -ne 0) {
  Write-Warning "Superset non e' ancora pronto. Controlla: kubectl get pods -n $Ns ; kubectl logs -n $Ns deploy/superset -c init"
}

Write-Host ""
Write-Host "Fatto."
Write-Host "  Apri il port-forward:  .\scripts\forward.ps1   ->  http://localhost:8088"
Write-Host "  Utente: admin"
if ($adminPassword) {
  Write-Host "  Password: $adminPassword   (copiala; poi la ritrovi con .\scripts\password.ps1)"
} else {
  Write-Host "  Password: .\scripts\password.ps1"
}
Write-Host "  Ollama: $OllamaUrl  modello: $Model"

if ($Forward) { & (Join-Path $PSScriptRoot "forward.ps1") }
