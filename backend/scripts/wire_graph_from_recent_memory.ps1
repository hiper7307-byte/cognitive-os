$ErrorActionPreference = "Stop"

$h = @{ "X-User-Id"="local-dev"; "Content-Type"="application/json" }

$recent = Invoke-RestMethod -Uri "http://127.0.0.1:8000/memory/recent?limit=25" -Method Get -Headers $h
if (-not $recent.results) {
  Write-Host "No recent memory rows found."
  exit 0
}

foreach ($m in $recent.results) {
  $content = [string]$m.content
  if ([string]::IsNullOrWhiteSpace($content)) { continue }

  $body = @{
    content = $content
    source_memory_id = $m.id
  } | ConvertTo-Json -Depth 8

  try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/cognitive/graph/ingest" -Method Post -Headers $h -Body $body | Out-Null
  } catch {
    Write-Host "ingest failed for memory id=$($m.id): $($_.Exception.Message)"
  }
}

Write-Host "Graph ingest from recent memory complete."
