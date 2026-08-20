# PP-StructureV3 OCR

本项目提供两种本地入口：

- `app.py`：Streamlit 上传测试页
- `api_app.py`：FastAPI OCR 服务

核心识别引擎是 `PP-StructureV3`，接口返回 PaddleX 的原始 JSON-safe 结果，Java 端自行解析。

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

支持上传图片和 PDF，页面会显示文件预览和原始 JSON。

## API 服务

```powershell
uvicorn api_app:app --host 0.0.0.0 --port 8000
```

健康检查：

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

通用结构识别：

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/ocr/structure `
  -H "Content-Type: application/json" `
  -d "{\"orderNo\":\"ORDER-1\",\"fileBase64\":\"...\"}"
```

历史兼容路径仍然保留：

- `/api/v1/ocr/id-card`
- `/api/v1/ocr/business-license`

这两个路径现在也返回原始 JSON，不再做身份证/营业执照字段封装。

请求字段优先级：

1. `fileBase64`
2. `fileUrl`
3. `imageBase64`
4. `imageUrl`

`fileBase64` 和 `fileUrl` 支持图片和 PDF。`imageBase64` / `imageUrl` 作为旧字段兼容保留。

## 返回值

成功时直接返回 PP-StructureV3 结果：

```json
{
  "res": {
    "input_path": "upload.png",
    "rec_texts": ["示例"]
  }
}
```

PDF 多页时返回数组。

失败时保持统一错误包：

```json
{
  "msg": "参数错误",
  "success": false,
  "code": 400,
  "data": {
    "result": 1,
    "orderNo": "ORDER-1"
  }
}
```

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall app.py api_app.py ocr_api scripts tests
```

