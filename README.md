# PP-StructureV3 Layout Parsing

本项目提供两种本地入口：

- `app.py`：Streamlit 上传测试页
- `api_app.py`：FastAPI 服务化接口

识别引擎是 `PP-StructureV3`，并显式使用 `PP-OCRv6_medium_det` / `PP-OCRv6_medium_rec` 作为文字检测和文字识别子模型。FastAPI 识别接口对齐 PaddleOCR 基础服务化部署的 `/layout-parsing` 形状。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install paddlepaddle -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install -r requirements.txt
```

## 本地页面

```powershell
streamlit run app.py
```

支持上传图片和 PDF，页面会显示文件预览和服务化响应 JSON。

## API 服务

```powershell
uvicorn api_app:app --host 0.0.0.0 --port 8000
```

健康检查保留原路径：

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

结构解析接口：

```powershell
curl -X POST http://127.0.0.1:8000/layout-parsing `
  -H "Content-Type: application/json" `
  -d "{\"file\":\"...\",\"fileType\":1}"
```

请求字段：

- `file`：图片/PDF Base64、data URL，或公网 URL
- `fileType`：可选，`0` 表示 PDF，`1` 表示图片；为空时按文件内容推断
- `visualize`：可选，保留官方字段
- `useTableRecognition` 等 PP-StructureV3 开关：可选，传入时覆盖单次推理配置

成功响应：

```json
{
  "logId": "f95f7ce5d04e40ecb9f0d1d7ca96ef46",
  "errorCode": 0,
  "errorMsg": "Success",
  "result": {
    "layoutParsingResults": [
      {
        "prunedResult": {
          "parsing_res_list": []
        },
        "markdown": null,
        "outputImages": {},
        "inputImage": null,
        "pageIndex": null
      }
    ],
    "dataInfo": {
      "fileType": 1
    }
  }
}
```

失败响应：

```json
{
  "logId": "7ed228165e194695931100e0fd7f1e35",
  "errorCode": 400,
  "errorMsg": "Bad Request"
}
```

## 配置

默认模型组合：

- `OCR_DETECTION_MODEL=PP-OCRv6_medium_det`
- `OCR_RECOGNITION_MODEL=PP-OCRv6_medium_rec`

其他常用环境变量：

- `OCR_DEVICE`：为空时自动检测，GPU 可设置为 `gpu:0`
- `MODEL_CACHE_DIR`：模型缓存目录
- `OCR_CPU_THREADS`：PP-StructureV3 CPU 推理线程数，默认 `4`
- `MAX_FILE_BYTES`：上传/下载文件大小限制
- `LOG_LEVEL`：日志级别

## 并发测试

```powershell
.\.venv\Scripts\python.exe scripts\concurrent_ocr_benchmark.py `
  --files F:\test\a.png F:\test\b.pdf `
  --concurrency 4 `
  --total 20 `
  --timeout 300
```

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall app.py api_app.py ocr_api scripts tests
```
