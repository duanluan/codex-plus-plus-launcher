param(
    [switch]$UseUv
)

$ErrorActionPreference = 'Stop'

$PackageRef = if ($env:CODEXPP_WRAPPER_PIP_SPEC) { $env:CODEXPP_WRAPPER_PIP_SPEC } else { 'https://github.com/duanluan/codex-plus-plus-launcher/archive/refs/heads/main.zip' }
$GitHubMirrorPrefixes = @(
    'https://gh-proxy.com/',
    'https://ghproxy.net/',
    'https://ghfast.top/',
    'https://fastgit.cc/'
)

function Get-AppLanguage {
    foreach ($value in @($env:CODEXPP_LANG, $env:LC_ALL, $env:LC_MESSAGES, $env:LANG)) {
        if ($value) {
            $normalized = $value.Split('.')[0].ToLower().Replace('-', '_')
            if ($normalized.StartsWith('zh')) {
                return 'zh'
            }
            break
        }
    }
    return 'en'
}

function Get-Text {
    param([string]$Key)

    switch ("$(Get-AppLanguage):$Key") {
        'zh:using_uv' { return 'using uv tool install' }
        'zh:using_pip' { return 'using pip install' }
        'zh:installed_try' { return 'installed successfully, next: cxpp install-app' }
        'zh:pip_requires_writable_env' { return 'current Python environment is not writable; run in an elevated or writable environment.' }
        'zh:missing_python' { return 'missing command: python or py' }
        'zh:missing_installer' { return 'missing installer: pip' }
        'zh:uv_requires_opt_in' { return 'uv install is opt-in. Re-run with -UseUv.' }
        'zh:retrying_mirror' { return 'direct GitHub download failed, retrying with mirrors' }
        'zh:retrying_force_reinstall' { return 'detected a broken pip installation record, retrying without uninstall' }
        'en:using_uv' { return 'using uv tool install' }
        'en:using_pip' { return 'using pip install' }
        'en:installed_try' { return 'installed successfully, next: cxpp install-app' }
        'en:pip_requires_writable_env' { return 'current Python environment is not writable; run in an elevated or writable environment.' }
        'en:missing_python' { return 'missing command: python or py' }
        'en:missing_installer' { return 'missing installer: pip' }
        'en:uv_requires_opt_in' { return 'uv install is opt-in. Re-run with -UseUv.' }
        'en:retrying_mirror' { return 'direct GitHub download failed, retrying with mirrors' }
        'en:retrying_force_reinstall' { return 'detected a broken pip installation record, retrying without uninstall' }
        default { return $Key }
    }
}

function Get-PythonCommand {
    foreach ($candidate in @('python', 'py')) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            return $candidate
        }
    }
    throw (Get-Text 'missing_python')
}

function Test-GitHubSpec {
    param([string]$Spec)

    return $Spec.StartsWith('https://github.com/') -or $Spec.StartsWith('https://raw.githubusercontent.com/')
}

function Test-ShouldRetryWithMirror {
    param([string]$Output)

    $Lowered = $Output.ToLowerInvariant()
    foreach ($pattern in @(
        'github.com',
        'raw.githubusercontent.com',
        'read timed out',
        'connect timeout',
        'max retries exceeded',
        'failed to establish a new connection',
        'temporarily unavailable',
        'connection reset'
    )) {
        if ($Lowered.Contains($pattern)) {
            return $true
        }
    }
    return $false
}

function Test-ShouldForceReinstall {
    param([string]$Output)

    $Lowered = $Output.ToLowerInvariant()
    return $Lowered.Contains('uninstall-no-record-file') -or $Lowered.Contains('no record file was found')
}

function Get-PipInstallArguments {
    param(
        [string]$Spec,
        [bool]$ForceReinstall = $false
    )

    $Args = [System.Collections.Generic.List[string]]::new()
    $Args.Add('-m')
    $Args.Add('pip')
    $Args.Add('install')
    if ($ForceReinstall) {
        $Args.Add('--ignore-installed')
        $Args.Add('--no-deps')
    } else {
        $Args.Add('--upgrade')
    }
    $Args.Add($Spec)
    return $Args.ToArray()
}

function Test-PythonEnvironmentWritable {
    param([string]$PythonCommand)

    $probeCode = @"
import pathlib, sysconfig
path = pathlib.Path(sysconfig.get_path('purelib'))
probe = path / '.__codexpp_write_probe__'
probe.write_text('ok', encoding='utf-8')
probe.unlink()
"@

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $PythonCommand -c $probeCode *> $null
        $status = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    return $status -eq 0
}

function Install-WithPipFallback {
    param([string]$PythonCommand)

    $Candidates = [System.Collections.Generic.List[string]]::new()
    $Candidates.Add($PackageRef)

    if ($env:CODEXPP_DISABLE_GITHUB_MIRROR -ne '1' -and (Test-GitHubSpec -Spec $PackageRef)) {
        foreach ($prefix in $GitHubMirrorPrefixes) {
            $Candidates.Add("${prefix}${PackageRef}")
        }
    }

    for ($i = 0; $i -lt $Candidates.Count; $i++) {
        $candidate = $Candidates[$i]
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $output = & $PythonCommand @(Get-PipInstallArguments -Spec $candidate) 2>&1
            $status = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousPreference
        }
        if ($output) {
            $output | Write-Host
        }
        if ($status -ne 0 -and (Test-ShouldForceReinstall -Output ($output | Out-String))) {
            Write-Host (Get-Text 'retrying_force_reinstall')
            $previousPreference = $ErrorActionPreference
            $ErrorActionPreference = 'Continue'
            try {
                $output = & $PythonCommand @(Get-PipInstallArguments -Spec $candidate -ForceReinstall $true) 2>&1
                $status = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $previousPreference
            }
            if ($output) {
                $output | Write-Host
            }
        }
        if ($status -eq 0) {
            return
        }
        if ($i -lt ($Candidates.Count - 1) -and (Test-ShouldRetryWithMirror -Output ($output | Out-String))) {
            Write-Host (Get-Text 'retrying_mirror')
            continue
        }
        throw ($output | Out-String)
    }
}

function Get-UvBinDirectory {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & uv tool dir --bin 2>&1
        $status = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($status -ne 0) {
        return $null
    }
    $path = ($output | Out-String).Trim()
    if ($path) {
        return $path
    }
    return $null
}

function Remove-BrokenWindowsNpmShims {
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCommand) {
        return
    }

    $nodeDir = Split-Path -Parent $nodeCommand.Source
    $packageRoot = Join-Path $nodeDir 'node_modules\@duanluan\codex-plus-plus-launcher'
    if (Test-Path -LiteralPath $packageRoot) {
        return
    }

    foreach ($commandName in @('cxpp', 'codexpp', 'codex-plus-plus-launcher')) {
        foreach ($extension in @('', '.cmd', '.ps1')) {
            $candidate = Join-Path $nodeDir ($commandName + $extension)
            if (Test-Path -LiteralPath $candidate) {
                Remove-Item -LiteralPath $candidate -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

function Invoke-Main {
    Remove-BrokenWindowsNpmShims
    $python = Get-PythonCommand
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $python -m pip --version *> $null
        $pipStatus = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($pipStatus -ne 0) {
        if ($UseUv -and (Get-Command uv -ErrorAction SilentlyContinue)) {
            Write-Host (Get-Text 'using_uv')
            & uv tool install --refresh $PackageRef
            Write-Host (Get-Text 'installed_try')
            return $LASTEXITCODE
        }
        if ($UseUv) {
            throw (Get-Text 'missing_installer')
        }
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            throw (Get-Text 'uv_requires_opt_in')
        }
        throw (Get-Text 'missing_installer')
    }

    Write-Host (Get-Text 'using_pip')
    if (-not (Test-PythonEnvironmentWritable -PythonCommand $python)) {
        throw (Get-Text 'pip_requires_writable_env')
    }
    Install-WithPipFallback -PythonCommand $python
    Write-Host (Get-Text 'installed_try')
    return $LASTEXITCODE
}

$invokedByExpression = -not $MyInvocation.MyCommand.Path
$dotSourced = $MyInvocation.InvocationName -eq '.'
$exitCode = Invoke-Main
if ($invokedByExpression -or $dotSourced) {
    return
}
exit $exitCode
