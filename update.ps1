# Scrape on this PC and push to GitHub (use if GitHub Actions gets blocked).
Set-Location $PSScriptRoot
python -m scraper.run
if ($LASTEXITCODE -ne 0) { Write-Host "Scrape failed"; exit 1 }
git add docs/data
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) { Write-Host "No changes"; exit 0 }
git commit -m "Update prices $(Get-Date -Format yyyy-MM-dd) (local)"
git pull --rebase
git push
