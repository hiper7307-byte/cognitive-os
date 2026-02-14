param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$UserId = "local-dev"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$h = @{
  "X-User-Id"   = $UserId
  "Content-Type"= "application/json"
}

Write-Host "== /health =="
Invoke-RestMethod "$BaseUrl/health" | ConvertTo-Json -Depth 8

Write-Host "== write semantic notes =="
@(
  @{ text = "save note meta eval check: architecture consistency improves maintainability" },
  @{ text = "save note meta eval check: stable contracts reduce regressions" }
) | ForEach-Object {
  $body = $_ | ConvertTo-Json -Depth 8
  Invoke-RestMethod "$BaseUrl/task" -Method Post -Headers $h -Body $body | Out-Null
}
Write-Host "notes written"

Write-Host "== /llm/chat x3 =="
@(
  "Given prior notes, should I keep one architecture?",
  "What do my notes imply about maintainability?",
  "Summarize architecture guidance from memory."
) | ForEach-Object {
  $b = @{
    message      = $_
    use_memory   = $true
    memory_limit = 8
  } | ConvertTo-Json -Depth 8

  $resp = Invoke-RestMethod "$BaseUrl/llm/chat" -Method Post -Headers $h -Body $b
  [pscustomobject]@{
    ok          = $resp.ok
    memory_used = $resp.memory_used
    mode        = $resp.arbitration.mode
    msg_preview = ($resp.message -replace "`r`n"," ") -replace "`n"," "
  } | ConvertTo-Json -Depth 6
}

Write-Host "== /cognitive/meta-eval/recent =="
$recent = Invoke-RestMethod "$BaseUrl/cognitive/meta-eval/recent?limit=10" -Headers $h
$recent | ConvertTo-Json -Depth 12

if (-not $recent.ok -or $recent.count -lt 1) {
  throw "meta-eval recent returned no events"
}

Write-Host "== /cognitive/meta-eval/stats =="
$stats = Invoke-RestMethod "$BaseUrl/cognitive/meta-eval/stats?window=50" -Headers $h
$stats | ConvertTo-Json -Depth 12

if (-not $stats.ok -or $stats.total -lt 1) {
  throw "meta-eval stats invalid"
}

Write-Host "PASS: meta-eval layer verified"
