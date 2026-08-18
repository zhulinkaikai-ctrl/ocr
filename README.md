# OCR 本地 Demo

本项目提供 PaddleOCR-VL-1.6 的本地调试页面和 FastAPI 服务，用于识别居民身份证和营业执照图片，并直接返回模型原始 JSON。业务字段提取和最终响应封装由 Java 调用方负责。

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

本地测试建议使用 `.env.local` 启动上传页面，这样会使用本机 GPU 并启用图片压缩：

```powershell
.\scripts\start-demo.ps1 -EnvFile .env.local
```

浏览器打开 Streamlit 给出的本地地址，上传身份证或营业执照图片后点击识别按钮。

第一次运行时，PaddleOCR-VL-1.6 的模型缓存会放在项目目录下的 `.paddlex_cache/`。

## API 服务

启动 FastAPI 服务：

```powershell
copy .env.local.example .env.local
.\scripts\start-api.ps1 -EnvFile .env.local -BindHost 0.0.0.0 -Port 8000
```

本地测试环境默认使用 `gpu:0`，并通过 `OCR_COMPRESS_MAX_SIDE=640` 压缩图片；正式环境使用 `.env.prod.example`，默认 GPU 且不压缩图片。

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

成功时页面和 API 都直接展示 PaddleOCR-VL 原始 JSON，例如：

```json
{
  "res": {
    "input_path": null,
    "page_index": null,
    "page_count": null,
    "parsing_res_list": []
  }
}
```

Python 服务不解析身份证或营业执照字段，也不返回 `info`、`content` 等业务结构。Java 可以根据 `res.parsing_res_list` 及其他模型字段自行提取并封装。

参数错误和 OCR 异常仍返回统一失败结构，详见 `docs/requirements/2026-08-13-ocr-api.md`。

## 隐私

上传图片只在当前 Streamlit 会话内存中处理。当前版本不写入数据库，也不保存上传文件或识别记录。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall app.py id_card_ocr tests
```
