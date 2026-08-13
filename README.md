# 身份证 OCR 本地 Demo

本项目是一个本地运行的 Streamlit Demo，用 PaddleOCR 识别单张居民身份证正面或反面图片，并输出结构化字段。

## 安装

建议使用 Python 3.10 或 3.11 创建虚拟环境。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install paddlepaddle -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install -r requirements.txt
```

## 启动

```powershell
streamlit run app.py
```

浏览器打开 Streamlit 给出的本地地址，上传身份证单面图片后点击“开始识别”。

第一次运行时，PaddleOCR 的模型缓存会放在项目目录下的 `.paddlex_cache/`。

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
