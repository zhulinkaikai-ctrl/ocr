# PaddleOCR-VL 本地测试

这个项目只保留一个轻量上传测试页。模型由本机或服务器上的 PaddleOCR-VL Docker Compose 服务运行，Python 不再直接加载 `paddleocr` / `paddlepaddle`。

职责划分：

- Docker Compose：启动 PaddleOCR-VL 模型服务。
- Python 上传页：上传图片/PDF，调用本机模型服务，展示官方原始 JSON。
- Java 系统：正式调用同一个模型服务，拿 JSON 后自行解析身份证、营业执照、发票字段。

## 启动模型服务

准备 `.env`：

```powershell
copy .env.example .env
```

启动官方 PaddleOCR-VL 服务：

```powershell
docker compose up -d
```

健康检查：

```powershell
curl http://127.0.0.1:8080/health
```

官方识别接口：

```text
POST http://127.0.0.1:8080/layout-parsing
```

请求体是 JSON，图片或 PDF 内容放在 `file` 字段中，使用 Base64 编码。`fileType=0` 表示 PDF，`fileType=1` 表示图片。

## 启动上传页

安装 Python 测试页依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

启动页面：

```powershell
streamlit run app.py
```

页面支持上传：

- 身份证图片/PDF
- 营业执照图片/PDF
- 发票图片/PDF

上传页不解析字段，只展示 PaddleOCR-VL 服务返回的原始 JSON。

## Java 调用

Java 生产环境直接调用 Docker Compose 暴露的服务地址：

```text
http://服务器IP:8080/layout-parsing
```

Java 侧负责：

- Base64 编码图片或 PDF。
- 设置 `fileType`。
- 解析 PaddleOCR-VL 原始 JSON。
- 封装业务响应。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app.py env_file.py ocr_client.py ocr_settings.py tests
```
