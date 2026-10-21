# Builda as imagens da api e do worker e importa no no do kind (Docker Desktop).
# O cluster kind usa um containerd proprio e nao enxerga as imagens do Docker local.
$ErrorActionPreference = "Stop"

$node = "desktop-control-plane"
$images = @("conversorarquivos-api:latest", "conversorarquivos-worker:latest")
$tmp = Join-Path $env:TEMP "conversor-images.tar"

docker compose build api worker
if ($LASTEXITCODE -ne 0) { throw "docker compose build falhou" }


docker save -o $tmp @images
if ($LASTEXITCODE -ne 0) { throw "docker save falhou" }                # docker save via arquivo: o pipe do PowerShell 5.1 corrompe dados binarios

try {
    docker cp $tmp "${node}:/conversor-images.tar"
    if ($LASTEXITCODE -ne 0) { throw "docker cp falhou" }
    docker exec $node ctr -n k8s.io images import /conversor-images.tar
    if ($LASTEXITCODE -ne 0) { throw "ctr import falhou" }
    docker exec $node rm -f /conversor-images.tar
}
finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
}

Write-Host "Imagens carregadas. Se os pods ja existem: kubectl -n conversor rollout restart deploy/api deploy/worker"
