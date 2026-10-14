<#
.SYNOPSIS
  Sign Windows binaries -- or do nothing when no credentials are configured.

.DESCRIPTION
  Called by scripts/build_desktop.py for the app folder and again for the
  installer. Unsigned builds are the default (see DESKTOP_PLAN.md, "Unsigned
  builds"); turning signing on needs credentials, not code changes.

  WINDOWS_SIGNING_MODE selects the method:
    (unset)  skip signing; exit 0
    pfx      a code-signing certificate file:
               WINDOWS_PFX_PATH or WINDOWS_PFX_BASE64, plus WINDOWS_PFX_PASSWORD
    azure    Azure Artifact Signing (Trusted Signing) through signtool's dlib:
               AZURE_SIGNING_DLIB      path to Azure.CodeSigning.Dlib.dll
               AZURE_SIGNING_METADATA  path to the metadata.json (endpoint,
                                       account, certificate profile)
               plus AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET
               for the service principal.

  Every .exe, .dll and .pyd is signed (Smart App Control checks each one).
#>
param([Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)][string[]]$Paths)

$ErrorActionPreference = "Stop"
$mode = $env:WINDOWS_SIGNING_MODE
if (-not $mode) {
  Write-Host "Windows signing skipped: WINDOWS_SIGNING_MODE is not set (unsigned build)."
  exit 0
}

$signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
  Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
if (-not $signtool) { throw "signtool.exe not found (install the Windows SDK)." }

$files = foreach ($p in $Paths) {
  if (Test-Path $p -PathType Container) {
    Get-ChildItem $p -Recurse -File -Include *.exe, *.dll, *.pyd | Select-Object -ExpandProperty FullName
  } else { (Resolve-Path $p).Path }
}
$timestamp = @("/tr", "http://timestamp.digicert.com", "/td", "sha256", "/fd", "sha256")

switch ($mode) {
  "pfx" {
    $pfx = $env:WINDOWS_PFX_PATH
    if (-not $pfx) {
      $pfx = Join-Path $env:RUNNER_TEMP "codesign.pfx"
      [IO.File]::WriteAllBytes($pfx, [Convert]::FromBase64String($env:WINDOWS_PFX_BASE64))
    }
    $auth = @("/f", $pfx, "/p", $env:WINDOWS_PFX_PASSWORD)
  }
  "azure" {
    $auth = @("/dlib", $env:AZURE_SIGNING_DLIB, "/dmdf", $env:AZURE_SIGNING_METADATA)
  }
  default { throw "Unknown WINDOWS_SIGNING_MODE '$mode' (expected pfx or azure)." }
}

# signtool accepts many files per call; batch to keep command lines short.
for ($i = 0; $i -lt $files.Count; $i += 50) {
  $batch = $files[$i..([Math]::Min($i + 49, $files.Count - 1))]
  & $signtool sign @auth @timestamp /d "Transcribe-HTR" @batch
  if ($LASTEXITCODE -ne 0) { throw "signtool failed ($LASTEXITCODE)." }
}
Write-Host "Signed $($files.Count) file(s) with mode '$mode'."
