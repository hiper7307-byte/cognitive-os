$ErrorActionPreference = "Stop"

$h = @{ "X-User-Id"="local-dev"; "Content-Type"="application/json" }

Write-Host "== /health =="
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get | ConvertTo-Json -Depth 6

Write-Host "== ingest sample graph text =="
$ing = @{
  content = "AI Task OS depends on memory governance. Memory governance supports identity consistency. Identity consistency supports long-term thinking."
} | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri "http://127.0.0.1:8000/cognitive/graph/ingest" -Method Post -Headers $h -Body $ing | ConvertTo-Json -Depth 10

Write-Host "== list nodes =="
$nodes = Invoke-RestMethod -Uri "http://127.0.0.1:8000/cognitive/graph/nodes?limit=20" -Method Get -Headers $h
$nodes | ConvertTo-Json -Depth 10

if (-not $nodes.nodes -or $nodes.nodes.Count -eq 0) {
  throw "No graph nodes found after ingest."
}

$startId = $nodes.nodes[0].id
Write-Host "== traverse from node id = $startId =="

$q = @{
  start_node_id = $startId
  max_hops = 2
  per_hop_limit = 50
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Uri "http://127.0.0.1:8000/cognitive/graph/query" -Method Post -Headers $h -Body $q | ConvertTo-Json -Depth 12
