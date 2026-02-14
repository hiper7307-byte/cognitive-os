$ErrorActionPreference = "Stop"

Write-Host "== HEALTH ==" -ForegroundColor Cyan
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health" | Format-List

Write-Host "== TASK ==" -ForegroundColor Cyan
$taskHeaders = @{ "Content-Type" = "application/json" }
$taskBody = @{ text = "save note smoke test pass $(Get-Date -Format s)" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/task" -Headers $taskHeaders -Body $taskBody | Format-List

Write-Host "== MEMORY QUERY ==" -ForegroundColor Cyan
$qBody = @{ query = "smoke test pass"; types = @("semantic","episodic","procedural"); limit = 5 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/memory/query" -Headers $taskHeaders -Body $qBody | Format-List

Write-Host "== LLM CHAT ==" -ForegroundColor Cyan
$llmBody = @{
  message = "Give me 3 execution tasks for platform hardening"
  use_memory = $true
  memory_limit = 8
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/llm/chat" -Headers $taskHeaders -Body $llmBody | Format-List

Write-Host "== RECENT MEMORY ==" -ForegroundColor Cyan
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/memory/recent?limit=8" |
  Select-Object -ExpandProperty results |
  Select-Object id,memory_type,source_task_id,created_at,content |
  Format-Table -Wrap
