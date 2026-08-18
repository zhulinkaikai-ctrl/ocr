# OCR 服务手动部署文档

本文档说明如何在不使用 Docker 的情况下部署 OCR API 服务。当前推荐部署方式是：

```text
Java 业务系统 -> HTTP 调用 -> Python FastAPI OCR 服务 -> PaddleOCR-VL-1.6 模型
```

生产环境主要部署 `api_app.py` 提供的 FastAPI 服务；`app.py` 是本地上传调试页面，可以按需启动。

## 一、部署包内容

打包发布时建议包含：

```text
api_app.py
app.py
id_card_ocr/
ocr_api/
requirements-prod.txt
.env.example
.env.local.example
.env.prod.example
scripts/
deploy/
docs/deploy-manual.md
README.md
```

不要打包：

```text
.venv/
.git/
.idea/
__pycache__/
*.log
```

`.paddlex_cache/` 是否打包取决于服务器能否联网：

- 服务器能联网：可以不打包，首次预加载时自动下载模型。
- 服务器不能联网：需要提前准备模型缓存，并把 `MODEL_CACHE_DIR` 指向该目录。

## 二、通用配置说明

部署前复制 `.env.prod.example` 为 `.env`。本地测试可以复制 `.env.local.example` 为 `.env.local`。

```text
OCR_DEVICE=gpu:0
OCR_ENGINE=paddleocr_vl
MODEL_CACHE_DIR=.paddlex_cache
OCR_COMPRESS_MAX_SIDE=
MAX_IMAGE_BYTES=10485760
LOG_LEVEL=INFO
```

配置说明：

- `OCR_DEVICE`：OCR 运行设备。GPU 服务器填 `gpu:0`；留空则自动判断。
- `OCR_ENGINE`：当前分支固定使用 `paddleocr_vl`，也就是 PaddleOCR-VL-1.6。
- `MODEL_CACHE_DIR`：PaddleOCR-VL 模型缓存目录，生产环境可以改成绝对路径。
- `OCR_COMPRESS_MAX_SIDE`：本地测试图片压缩开关。正式环境留空；本地 4GB 显存机器建议先填 `640`，跑通后再尝试调高。
- `MAX_IMAGE_BYTES`：单张图片最大字节数，默认 10MB。
- `LOG_LEVEL`：日志级别，生产环境建议 `INFO`。

## 三、Windows 部署

### 1. 服务器环境

建议：

- Windows Server 或 Windows 10/11。
- Python 3.10 或 3.11。
- GPU 部署时先安装好显卡驱动，并确认 Paddle GPU 版本能正常运行。

### 2. 解压项目

示例目录：

```text
D:\services\tesrtOCR
```

后续命令都在项目根目录执行。

### 3. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-prod.txt
```

如果服务器不使用 GPU，需要把 `requirements-prod.txt` 里的 `paddlepaddle-gpu` 换成对应 CPU 版 Paddle。

### 4. 配置 `.env`

```powershell
copy .env.prod.example .env
notepad .env
```

GPU 示例：

```text
OCR_DEVICE=gpu:0
OCR_ENGINE=paddleocr_vl
MODEL_CACHE_DIR=D:\services\tesrtOCR\.paddlex_cache
OCR_COMPRESS_MAX_SIDE=
MAX_IMAGE_BYTES=10485760
LOG_LEVEL=INFO
```

CPU 示例：

```text
OCR_DEVICE=
OCR_ENGINE=paddleocr_vl
MODEL_CACHE_DIR=D:\services\tesrtOCR\.paddlex_cache
OCR_COMPRESS_MAX_SIDE=640
MAX_IMAGE_BYTES=10485760
LOG_LEVEL=INFO
```

### 5. 预加载 OCR 模型

```powershell
.\.venv\Scripts\python.exe scripts\preload-ocr.py
```

这一步用于提前下载/加载 PaddleOCR-VL-1.6 模型，避免第一次 Java 请求耗时过长。

### 6. 手动启动 API

```powershell
.\scripts\start-api.ps1 -EnvFile .env -BindHost 0.0.0.0 -Port 8000
```

验证服务：

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

接口文档：

```text
http://服务器IP:8000/docs
```

### 7. 注册为 Windows 服务

如果需要服务开机自启，推荐用 NSSM。

示例：

```powershell
.\deploy\windows\install-nssm-service.ps1 `
  -ProjectRoot "D:\services\tesrtOCR" `
  -NssmPath "C:\tools\nssm\nssm.exe" `
  -Port 8000
```

启动服务：

```powershell
nssm start OCRApi
```

查看服务状态：

```powershell
nssm status OCRApi
```

## 四、Linux 部署

### 1. 服务器环境

建议：

- Ubuntu / Debian / CentOS / Rocky Linux 均可。
- Python 3.10 或 3.11。
- GPU 部署时先安装好显卡驱动，并确认服务器可以正常使用 GPU。

### 2. 解压项目

示例目录：

```bash
/opt/tesrtOCR
```

进入项目目录：

```bash
cd /opt/tesrtOCR
```

### 3. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements-prod.txt
```

如果服务器不使用 GPU，需要把 `requirements-prod.txt` 里的 `paddlepaddle-gpu` 换成对应 CPU 版 Paddle。

### 4. 配置 `.env`

```bash
cp .env.prod.example .env
vi .env
```

GPU 示例：

```text
OCR_DEVICE=gpu:0
OCR_ENGINE=paddleocr_vl
MODEL_CACHE_DIR=/opt/tesrtOCR/.paddlex_cache
OCR_COMPRESS_MAX_SIDE=
MAX_IMAGE_BYTES=10485760
LOG_LEVEL=INFO
```

CPU 示例：

```text
OCR_DEVICE=
OCR_ENGINE=paddleocr_vl
MODEL_CACHE_DIR=/opt/tesrtOCR/.paddlex_cache
OCR_COMPRESS_MAX_SIDE=640
MAX_IMAGE_BYTES=10485760
LOG_LEVEL=INFO
```

### 5. 预加载 OCR 模型

```bash
./.venv/bin/python scripts/preload-ocr.py
```

### 6. 手动启动 API

```bash
bash scripts/start-api.sh .env
```

验证服务：

```bash
curl http://127.0.0.1:8000/api/v1/health
```

接口文档：

```text
http://服务器IP:8000/docs
```

### 7. 注册为 systemd 服务

复制服务模板：

```bash
sudo cp deploy/systemd/ocr-api.service.example /etc/systemd/system/ocr-api.service
```

编辑真实项目路径：

```bash
sudo vi /etc/systemd/system/ocr-api.service
```

把文件里的 `/opt/tesrtOCR` 改成实际部署目录。

加载并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable ocr-api
sudo systemctl start ocr-api
sudo systemctl status ocr-api
```

查看日志：

```bash
journalctl -u ocr-api -f
```

## 五、Java 调用验证

身份证接口：

```text
POST http://服务器IP:8000/api/v1/ocr/id-card
```

营业执照接口：

```text
POST http://服务器IP:8000/api/v1/ocr/business-license
```

请求体示例：

```json
{
  "orderNo": "ORDER-001",
  "imageBase64": "图片base64"
}
```

也可以传公网图片 URL：

```json
{
  "orderNo": "ORDER-002",
  "imageUrl": "https://example.com/test.jpg"
}
```

注意：`imageUrl` 只允许公网 HTTP/HTTPS 图片。内网地址、localhost、file 路径会被拒绝。Java 后端上传本地文件时，建议转成 Base64 调用。

## 六、部署前验证

部署前建议执行：

Windows：

```powershell
.\.venv\Scripts\python.exe -m compileall app.py api_app.py ocr_api id_card_ocr scripts tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux：

```bash
./.venv/bin/python -m compileall app.py api_app.py ocr_api id_card_ocr scripts tests
./.venv/bin/python -m unittest discover -s tests -v
```

## 七、常见问题

### 1. GPU 不生效

检查：

- `.env` 里的 `OCR_DEVICE` 是否为 `gpu:0`。
- Paddle GPU 版本是否和服务器显卡驱动/CUDA 环境匹配。
- 运行预加载脚本时是否显示 GPU 设备。

### 2. 第一次请求很慢

先执行：

```bash
python scripts/preload-ocr.py
```

首次运行可能会下载或初始化模型，这是正常现象。

### 3. Windows 报“页面文件太小”或 `os error 1455`

这是 Windows 在加载 PaddleOCR-VL-1.6 大模型时内存提交量不足导致的，通常不是接口代码问题。

处理建议：

- 关闭其他占用内存或显存的程序。
- 用 `nvidia-smi` 确认没有其他 Python 进程占用 GPU。
- 把 Windows 虚拟内存改成系统管理，或手动设置为 32GB 到 64GB。
- 修改虚拟内存后重启电脑，再执行 `python scripts/preload-ocr.py`。

当前项目使用 PaddleOCR-VL-1.6，4GB 显存机器可以尝试加载，但运行会比较吃紧。生产环境建议使用显存更大的 NVIDIA GPU。

### 4. oneDNN/PIR 报错

项目已在 `id_card_ocr/paddle_adapter.py` 中设置运行时参数：

```text
FLAGS_enable_pir_api=0
FLAGS_use_onednn=0
FLAGS_use_mkldnn=0
```

如果仍然报错，确认服务启动时使用的是最新代码。

### 5. Java 调用超时

建议 Java HTTP 客户端设置：

- 连接超时：5 秒左右。
- 读取超时：30 到 60 秒。
- 图片大小：尽量控制在 10MB 以内。

### 6. 无法访问服务

检查：

- 服务是否监听 `0.0.0.0:8000`。
- 服务器防火墙是否放行 8000 端口。
- Java 调用地址是否使用服务器真实 IP。
