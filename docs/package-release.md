# OCR 服务打包发布文档

本文档用于把当前项目打成一个可部署压缩包，例如：

```text
ocr-api-release.zip
```

该压缩包用于服务器手动部署，不包含 Docker，不包含本机 `.venv`。

## 一、打包原则

打包进去：

```text
api_app.py
app.py
id_card_ocr/
ocr_api/
tests/
requirements-prod.txt
.env.example
scripts/
deploy/
docs/
README.md
```

不打包：

```text
.venv/
.git/
.idea/
__pycache__/
*.pyc
*.log
.paddlex_cache/
```

说明：

- `.venv/` 不要打包，服务器上重新创建虚拟环境。
- `.paddlex_cache/` 默认不打包，服务器部署后用 `scripts/preload-ocr.py` 预加载模型。
- `tests/` 可以保留在发布包里，方便服务器部署后做验收测试。

## 二、Windows 打包

在项目根目录执行 PowerShell：

```powershell
$ReleaseRoot = ".release"
$ReleaseDir = "$ReleaseRoot\ocr-api"
$Package = "ocr-api-release.zip"

if (Test-Path $ReleaseRoot) {
    Remove-Item -Recurse -Force $ReleaseRoot
}

if (Test-Path $Package) {
    Remove-Item -Force $Package
}

New-Item -ItemType Directory -Force $ReleaseDir | Out-Null

Copy-Item api_app.py $ReleaseDir
Copy-Item app.py $ReleaseDir
Copy-Item requirements-prod.txt $ReleaseDir
Copy-Item .env.example $ReleaseDir
Copy-Item README.md $ReleaseDir

Copy-Item id_card_ocr $ReleaseDir -Recurse
Copy-Item ocr_api $ReleaseDir -Recurse
Copy-Item tests $ReleaseDir -Recurse
Copy-Item scripts $ReleaseDir -Recurse
Copy-Item deploy $ReleaseDir -Recurse
Copy-Item docs $ReleaseDir -Recurse

Get-ChildItem $ReleaseDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem $ReleaseDir -Recurse -File -Include "*.pyc","*.log" | Remove-Item -Force

Compress-Archive -Path "$ReleaseDir\*" -DestinationPath $Package -Force
```

打包完成后，项目根目录会生成：

```text
ocr-api-release.zip
```

## 三、Linux 打包

在项目根目录执行：

```bash
RELEASE_ROOT=".release"
RELEASE_DIR="$RELEASE_ROOT/ocr-api"
PACKAGE="ocr-api-release.zip"

rm -rf "$RELEASE_ROOT"
rm -f "$PACKAGE"

mkdir -p "$RELEASE_DIR"

cp api_app.py "$RELEASE_DIR/"
cp app.py "$RELEASE_DIR/"
cp requirements-prod.txt "$RELEASE_DIR/"
cp .env.example "$RELEASE_DIR/"
cp README.md "$RELEASE_DIR/"

cp -r id_card_ocr "$RELEASE_DIR/"
cp -r ocr_api "$RELEASE_DIR/"
cp -r tests "$RELEASE_DIR/"
cp -r scripts "$RELEASE_DIR/"
cp -r deploy "$RELEASE_DIR/"
cp -r docs "$RELEASE_DIR/"

find "$RELEASE_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$RELEASE_DIR" -type f \( -name "*.pyc" -o -name "*.log" \) -delete

(cd "$RELEASE_ROOT" && zip -r "../$PACKAGE" "ocr-api")
```

打包完成后会生成：

```text
ocr-api-release.zip
```

## 四、检查压缩包内容

Windows：

```powershell
Expand-Archive ocr-api-release.zip .release-check -Force
Get-ChildItem .release-check\ocr-api
```

Linux：

```bash
rm -rf .release-check
unzip ocr-api-release.zip -d .release-check
ls .release-check/ocr-api
```

至少应看到：

```text
api_app.py
id_card_ocr/
ocr_api/
requirements-prod.txt
.env.example
scripts/
deploy/
docs/
```

## 五、服务器部署入口

把 `ocr-api-release.zip` 复制到服务器后：

1. 解压。
2. 进入解压后的 `ocr-api` 目录。
3. 按 `docs/deploy-manual.md` 执行 Windows 或 Linux 部署步骤。

Windows 部署入口：

```powershell
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-prod.txt
.\.venv\Scripts\python.exe scripts\preload-ocr.py
.\scripts\start-api.ps1 -BindHost 0.0.0.0 -Port 8000
```

Linux 部署入口：

```bash
cp .env.example .env
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-prod.txt
./.venv/bin/python scripts/preload-ocr.py
bash scripts/start-api.sh
```

## 六、打包后验证

启动服务后访问：

```text
http://服务器IP:8000/api/v1/health
```

返回：

```json
{"status":200}
```

再访问接口文档：

```text
http://服务器IP:8000/docs
```

确认可以看到：

```text
/api/v1/ocr/id-card
/api/v1/ocr/business-license
```

## 七、常见问题

### 1. 为什么不直接打包 `.venv`

`.venv` 和本机路径、系统、Python 版本、GPU 环境强相关。复制到服务器后很容易无法运行，所以服务器上重新创建虚拟环境更稳。

### 2. 为什么不打包 `.paddlex_cache`

模型缓存较大，而且不同环境可能缓存路径不同。服务器能联网时，推荐部署后预加载。服务器不能联网时，再单独准备模型缓存。

### 3. Windows 打包命令提示权限问题

确认 PowerShell 当前目录是项目根目录，并且没有程序正在占用 `.release/` 或 `ocr-api-release.zip`。

### 4. Linux 没有 zip 命令

先安装：

```bash
sudo apt install zip unzip
```

或使用系统对应的软件包管理器安装 `zip`。
