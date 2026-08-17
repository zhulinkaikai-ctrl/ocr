# OCR 本地 Demo

本项目是一个本地运行的 Streamlit Demo，用 PaddleOCR-VL-1.6 识别居民身份证和营业执照图片，并输出结构化字段。

## 安装

建议使用 Python 3.10 或 3.11 创建虚拟环境。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install paddlepaddle-gpu
python -m pip install -r requirements.txt
```

## 启动

```powershell
streamlit run app.py
```

浏览器打开 Streamlit 给出的本地地址，在“身份证”或“营业执照”标签页上传图片后点击识别按钮。

第一次运行时，PaddleOCR-VL-1.6 的模型缓存会放在项目目录下的 `.paddlex_cache/`。

## API 服务

启动 FastAPI 服务：

```powershell
uvicorn api_app:app --host 0.0.0.0 --port 8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

健康检查：

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

身份证正面识别：

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/ocr/id-card `
  -H "Content-Type: application/json" `
  -d "{\"orderNo\":\"ORDER-1\",\"imageBase64\":\"...\"}"
```

营业执照识别：

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/ocr/business-license `
  -H "Content-Type: application/json" `
  -d "{\"orderNo\":\"ORDER-2\",\"imageUrl\":\"https://example.com/license.jpg\"}"
```

打包发布请看：`docs/package-release.md`

手动部署到服务器请看：`docs/deploy-manual.md`

## 输出

页面会展示：

- 图片预览
- 证件面判断
- 字段表格
- 字段校验状态
- 可复制 JSON
- 原始 OCR 文本

JSON 采用中英结合结构：

```json
{
  "证件类型": "居民身份证",
  "证件面": "正面",
  "字段": [
    {
      "key": "name",
      "label": "姓名",
      "value": "张三",
      "status": "通过",
      "confidence": 0.98
    }
  ],
  "原始文本": ["姓名张三"]
}
```

## 隐私

上传图片只在当前 Streamlit 会话内存中处理。当前版本不写入数据库，也不保存上传文件或识别记录。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall app.py id_card_ocr tests
```
