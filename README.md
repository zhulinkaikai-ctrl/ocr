# PaddleOCR-VL 本地测试

这个项目保留两种运行方式，但接口保持一致：

- 本地没有 Docker：Windows 原生 Python + FastAPI 加载 PaddleOCR-VL。
- 服务器有 Docker：使用 PaddleOCR-VL Docker Compose。

两种方式都暴露同一个接口：

```text
POST /layout-parsing
```

上传页和 Java 只需要调用这个接口，后续从本地 FastAPI 切到服务器 Docker 时不用改接口名。

## 本地 Windows 测试

准备环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install paddlepaddle-gpu
python -m pip install -r requirements.txt
copy .env.example .env
```

启动本地原生 FastAPI：

```powershell
uvicorn api_app:app --host 127.0.0.1 --port 8080
```

另开一个终端启动上传页：

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

本地服务地址：

```text
http://127.0.0.1:8080/layout-parsing
```

## 服务器 Docker 部署

服务器有 Docker 时直接使用 Compose：

```bash
cp .env.example .env
docker compose up -d
```

Java 调用：

```text
http://服务器IP:8080/layout-parsing
```

服务器不需要 Python 上传页代码；上传页只是你本地测试用。

## 接口格式

请求体是 JSON：

```json
{
  "file": "base64...",
  "fileType": 1,
  "visualize": false
}
```

字段说明：

- `file`：图片或 PDF 的 Base64。
- `fileType`：`0` 表示 PDF，`1` 表示图片。
- `visualize`：是否返回可视化结果，本地原生模式目前主要返回识别 JSON。

响应会放在：

```text
result.layoutParsingResults
```

上传页不解析字段，只展示 PaddleOCR-VL 返回的原始 JSON。Java 侧自己解析身份证、营业执照、发票字段。

## 上传页

页面支持上传：

- 身份证图片/PDF
- 营业执照图片/PDF
- 发票图片/PDF

## 配置

- `OCR_SERVICE_URL`：上传页调用的 OCR 服务地址。
- `OCR_DEVICE`：本地原生模式使用的设备，例如 `gpu:0` 或 `cpu`。
- `MODEL_CACHE_DIR`：PaddleOCR-VL 模型缓存目录。
- `OCR_COMPRESS_MAX_SIDE`：本地原生模式下可选图片压缩边长。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall -q api_app.py app.py env_file.py native_ocr.py ocr_client.py ocr_settings.py tests
```
