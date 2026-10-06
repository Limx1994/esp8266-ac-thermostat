#Requires -Version 5.1
[CmdletBinding(SupportsShouldProcess = $true)]
param([switch]$Apply = $true)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
$prefix = $root + '\'
$deleted = 0
$skipped = 0
$failed = 0
$freed = [long]0

function Assert-SafePath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "目标不在项目内：$full"
    }
    $current = $full
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "拒绝重解析点：$current"
            }
        }
        if ($current -eq $root) { break }
        $current = [IO.Path]::GetDirectoryName($current)
    }
}

function Get-SafeFiles([string]$Path) {
    Assert-SafePath $Path
    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.PSIsContainer) {
        $item
        return
    }
    foreach ($child in Get-ChildItem -LiteralPath $Path -Force) {
        if ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "拒绝重解析点：$($child.FullName)"
        }
        if ($child.PSIsContainer) {
            Get-SafeFiles $child.FullName
        } else {
            $child
        }
    }
}

function Find-Caches([string]$Path) {
    Assert-SafePath $Path
    foreach ($child in Get-ChildItem -LiteralPath $Path -Force) {
        if ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "缓存搜索遇到重解析点：$($child.FullName)"
        }
        if ($child.PSIsContainer) {
            if ($child.Name -eq '__pycache__') {
                $child.FullName.Substring($prefix.Length)
            } else {
                Find-Caches $child.FullName
            }
        }
    }
}

try {
    foreach ($marker in @('CMakeLists.txt', 'build.py', 'main\main.c', '.git')) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $marker))) {
            throw "项目标识缺失：$marker"
        }
    }
    $tracked = @(& git -C $root ls-files -z)
    if ($LASTEXITCODE -ne 0) { throw '无法读取 Git 跟踪文件，停止清理' }
    $tracked = @(($tracked -join "`n").Split([char]0) | Where-Object { $_ })
    $targets = @('build\s1_checkpoint', 'build\s1_build.log', 'build_ascii',
                 '__pycache__', 'tests\__pycache__', '.ninja_deps', '.ninja_log')
    foreach ($folder in @('main', 'components', 'tests')) {
        $path = Join-Path $root $folder
        if (Test-Path -LiteralPath $path -PathType Container) {
            $targets += @(Find-Caches $path)
        }
    }
    $targets = @($targets | Select-Object -Unique)
    $plans = @()
    foreach ($target in $targets) {
        $path = Join-Path $root $target
        Assert-SafePath $path
        $gitPath = $target.Replace('\', '/')
        foreach ($name in $tracked) {
            if ($name -eq $gitPath -or
                $name.StartsWith($gitPath + '/', [StringComparison]::OrdinalIgnoreCase)) {
                throw "清理目标包含 Git 跟踪文件：$name"
            }
        }
        if (-not (Test-Path -LiteralPath $path)) {
            $skipped++
            Write-Output "跳过：$target（不存在）"
            continue
        }
        $files = @(Get-SafeFiles $path)
        $bytes = [long]0
        foreach ($file in $files) { $bytes += $file.Length }
        $plans += [pscustomobject]@{Path=$path; Name=$target; Files=$files.Count; Bytes=$bytes}
    }
    $count = 0
    $total = [long]0
    foreach ($plan in $plans) {
        $count += $plan.Files
        $total += $plan.Bytes
        Write-Output "候选：$($plan.Name)，$($plan.Files) 个文件，$($plan.Bytes) 字节"
    }
    Write-Output "候选合计：$($plans.Count) 个目标，$count 个文件，$total 字节"
    foreach ($plan in $plans) {
        if (-not $Apply) {
            $skipped++
            Write-Output "跳过：$($plan.Name)（仅预览，使用 -Apply 执行）"
            continue
        }
        if (-not $PSCmdlet.ShouldProcess($plan.Path, '删除过程文件')) {
            $skipped++
            Write-Output "跳过：$($plan.Name)（WhatIf 或未确认）"
            continue
        }
        Assert-SafePath $plan.Path
        $files = @(Get-SafeFiles $plan.Path)
        $bytes = [long]0
        foreach ($file in $files) { $bytes += $file.Length }
        Remove-Item -LiteralPath $plan.Path -Recurse -Force -ErrorAction Stop
        if (Test-Path -LiteralPath $plan.Path) { throw "删除后目标仍存在：$($plan.Path)" }
        $deleted += $files.Count
        $freed += $bytes
        Write-Output "已删除：$($plan.Name)，$($files.Count) 个文件，$bytes 字节"
    }
} catch {
    $failed++
    [Console]::Error.WriteLine("清理失败：$($_.Exception.Message)；已停止后续删除，失败目标可能部分删除，未计入成功统计。")
}
Write-Output "结果：删除 $deleted 个文件，跳过 $skipped 个目标，失败 $failed 次，已确认释放 $freed 字节"
if ($failed) { exit 1 }
