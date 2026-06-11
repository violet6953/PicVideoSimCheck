#Requires -Version 5.1
<#
.SYNOPSIS
    自动发布 PicVideoSimCheck 到 GitHub Releases
.DESCRIPTION
    创建 GitHub Release 并上传 Output 目录下的安装程序
.NOTES
    1. 请先前往 GitHub 撤销已暴露的旧 Token
    2. 获取新 Token: https://github.com/settings/tokens/new
    3. 勾选权限: repo
    4. 将脚本中的 $Token 替换为新 Token
#>

# ==================== 配置区域 ====================

# 1. 填入你的 GitHub Personal Access Token（必须以 ghp_ 开头）
$Token = "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 2. 仓库信息
$Owner = "violet6953"
$Repo  = "PicVideoSimCheck"

# 3. Release 版本号
$TagName = "v1.0.2"

# 4. Release 标题
$ReleaseTitle = "PicSimProcess v1.0.2"

# 5. 要上传的文件（相对于脚本所在目录）
$Files = @(
    "Output\PicSimProcess_GPU_Setup_v1.0.2.exe",
    "Output\PicSimProcess_CPU_Setup_v1.0.2.exe"
)

# ==================== 脚本主体 ====================

$ErrorActionPreference = "Stop"

function Write-Step([string]$msg) {
    Write-Host "[+] $msg" -ForegroundColor Cyan
}

function Write-ErrorExit([string]$msg) {
    Write-Host "[!] $msg" -ForegroundColor Red
    exit 1
}

# 检查 Token
if ($Token -eq "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" -or [string]::IsNullOrWhiteSpace($Token)) {
    Write-ErrorExit "请先在脚本中设置你的 GitHub Personal Access Token`n获取方式: https://github.com/settings/tokens/new"
}

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 读取 Release 说明（从外部 Markdown 文件读取，避免 here-string 编码/解析问题）
$notesPath = Join-Path $ScriptDir "RELEASE_NOTES.md"
if (Test-Path $notesPath) {
    $ReleaseBody = [System.IO.File]::ReadAllText($notesPath, [System.Text.Encoding]::UTF8)
    Write-Step "已加载 Release 说明: $notesPath"
} else {
    $ReleaseBody = "Release $TagName"
    Write-Step "未找到 RELEASE_NOTES.md，使用默认说明"
}

# 检查文件是否存在
foreach ($file in $Files) {
    $fullPath = Join-Path $ScriptDir $file
    if (-not (Test-Path $fullPath)) {
        Write-ErrorExit "文件不存在: $fullPath"
    }
    $size = (Get-Item $fullPath).Length / 1GB
    Write-Step "找到文件: $file ($([math]::Round($size, 2)) GB)"
}

# 创建 Release
Write-Step "创建 Release: $TagName ..."
$headers = @{
    "Authorization" = "Bearer $Token"
    "Accept"        = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$body = @{
    tag_name         = $TagName
    name             = $ReleaseTitle
    body             = $ReleaseBody
    draft            = $false
    prerelease       = $false
    generate_release_notes = $false
} | ConvertTo-Json -Depth 10

try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$Repo/releases" `
        -Method Post -Headers $headers -Body $body -ContentType "application/json"
    Write-Step "Release 创建成功: $($release.html_url)"
} catch {
    $err = $_
    # 如果 Release 已存在，尝试获取它
    try {
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Owner/$Repo/releases/tags/$TagName" `
            -Headers $headers
        Write-Step "Release 已存在，使用现有 Release: $($release.html_url)"
    } catch {
        Write-ErrorExit "创建 Release 失败: $($err.Exception.Message)"
    }
}

# 提取上传 URL
$uploadUrl = $release.upload_url -replace "\{\?name,label\}", ""

# 上传文件
foreach ($file in $Files) {
    $fileName = Split-Path $file -Leaf
    $fullPath = Join-Path $ScriptDir $file
    $fileSize = (Get-Item $fullPath).Length

    Write-Step "上传: $fileName ($([math]::Round($fileSize / 1MB, 1)) MB) ..."

    # 检查是否已存在同名 asset
    $existingAsset = $release.assets | Where-Object { $_.name -eq $fileName }
    if ($existingAsset) {
        Write-Step "  同名文件已存在，先删除旧版本..."
        try {
            Invoke-RestMethod -Uri $existingAsset.url -Method Delete -Headers $headers | Out-Null
            Write-Step "  旧版本已删除"
        } catch {
            Write-Host "  警告: 删除旧版本失败，尝试继续上传..." -ForegroundColor Yellow
        }
    }

    $uploadHeaders = @{
        "Authorization" = "Bearer $Token"
        "Accept"        = "application/vnd.github+json"
        "Content-Type"  = "application/octet-stream"
    }

    $uri = "$uploadUrl?name=$fileName"

    try {
        $result = Invoke-RestMethod -Uri $uri -Method Post `
            -Headers $uploadHeaders `
            -InFile $fullPath
        Write-Step "上传成功: $($result.browser_download_url)"
    } catch {
        Write-ErrorExit "上传失败: $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  发布完成!" -ForegroundColor Green
Write-Host "  Release 页面: $($release.html_url)" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
