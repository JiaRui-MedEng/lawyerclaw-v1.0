# Vision 工具使用指南

## 📋 功能概述

百佑 LawyerClaw 现在支持图片分析和 OCR 文字提取功能，基于阿里百炼 `qwen3.5-plus` 多模态模型实现。

## 🛠️ 可用工具

### 1. `vision_analyze` - 图片分析工具

**功能**：分析图片内容，支持视觉问答、图片描述、场景理解等。

**参数**：
- `image_source` (必需): 图片源（**本地路径 或 HTTP/HTTPS URL**）
- `prompt` (可选): 分析问题或指令，默认"请描述这张图片"

**示例**：
```python
# 本地图片
result = await vision_analyze_tool(
    image_source="D:/images/document.png",
    prompt="图中有什么文字？"
)

# URL 图片
result = await vision_analyze_tool(
    image_source="https://example.com/image.jpg",
    prompt="描述这张图片"
)
```

**使用场景**：
- 图片内容描述
- 场景理解
- 视觉问答
- 图表分析
- 证件识别

---

### 2. `ocr_extract` - OCR 文字提取工具

**功能**：从图片中提取所有可见文字内容。

**参数**：
- `image_path` (必需): 图片文件路径

**示例**：
```python
# 自动 OCR（检测到图片时）
"📎 附件文件：D:/images/document.png\n提取图中的所有文字"

# 或使用工具调用
result = await ocr_tool("D:/images/document.png")
```

**使用场景**：
- 文档扫描识别
- 截图文字提取
- 照片中的文字识别
- 表格文字提取
- 手写体识别（尽力）

---

## 📝 使用方法

### 方法 1: 直接发送消息（推荐）

在聊天中直接发送带图片的消息：

```
📎 附件文件：
D:/path/to/your/image.png

请提取这张图片中的所有文字
```

或使用 URL：

```
图片 URL：https://example.com/image.jpg

请分析这张图片的内容
```

AI 会自动调用 Vision 工具进行分析。

---

### 方法 2: 使用专门的 OCR 指令

```
📎 附件文件：
D:/path/to/document.png

ocr_extract
```

这会触发专门的 OCR 工具，提取所有文字。

---

### 方法 3: 编程调用

```python
from service.tools.vision_tools import vision_analyze_tool, ocr_tool
import asyncio

async def main():
    # OCR 示例
    result = await ocr_tool("D:/images/document.png")
    if result["success"]:
        print(result["content"])
    
    # 图片分析示例
    result = await vision_analyze_tool(
        image_path="D:/images/scene.jpg",
        prompt="图中有什么人？他们在做什么？"
    )
    if result["success"]:
        print(result["content"])

asyncio.run(main())
```

---

## 🔧 配置

### 环境变量

确保 `.env` 文件中配置了正确的 API 信息：

```env
# LLM API — 阿里百炼（OpenAI 兼容接口）
OPENAI_API_KEY=sk-sp-76a2a41c31de4b7ebb7a7c797a0685ea
OPENAI_BASE_URL=https://coding.dashscope.aliyuncs.com/v1
OPENAI_MODEL=qwen3.5-plus
```

### 支持的图片格式

- ✅ JPG / JPEG
- ✅ PNG
- ✅ GIF
- ✅ BMP
- ✅ WebP

### 限制

- 最大文件大小：10MB
- 支持分辨率：模型自动处理
- 语言支持：中文、英文为主，支持多种语言

---

## 📊 测试

运行测试脚本验证功能：

```bash
# 1. 修改 test_vision_tools.py 中的图片路径
# 2. 运行测试
python test_vision_tools.py
```

测试包括：
1. OCR 文字提取
2. 图片内容分析
3. 视觉问答

---

## 💡 最佳实践

### 1. OCR 优化

对于文档扫描：
```
📎 附件文件：D:/scan/document.png

请提取这张图片中的所有文字，保持原有的段落格式和换行。
```

对于表格：
```
📎 附件文件：D:/images/table.png

这是一个表格，请提取所有文字并保持表格结构。
```

### 2. 图片分析优化

提供具体的问题：
```
❌ "描述这张图片"
✅ "图中有哪些人？他们的表情如何？背景是什么地方？"
```

### 3. 复杂场景

对于包含文字和图像的场景：
```
📎 附件文件：D:/images/mixed.png

1. 提取图片中的所有文字
2. 描述图片的整体场景
3. 说明文字和图像的关系
```

---

## ⚠️ 注意事项

1. **文件大小限制**：图片不能超过 10MB
2. **网络依赖**：需要联网调用 API
3. **识别准确率**：
   - 打印体文字：95%+
   - 手写体：70-90%（取决于清晰度）
   - 模糊/低分辨率：准确率下降
4. **语言支持**：主要支持中英文，其他语言效果可能不佳

---

## 🐛 故障排除

### 问题 1: "文件不存在"

**解决**：检查路径是否正确，使用绝对路径。

### 问题 2: "不支持的文件格式"

**解决**：确保是支持的图片格式（jpg/png/gif/bmp/webp）

### 问题 3: "图片过大"

**解决**：压缩图片到 10MB 以下。

### 问题 4: API 调用失败

**解决**：
1. 检查 `.env` 配置
2. 验证 API Key 是否有效
3. 检查网络连接

---

## 📚 技术实现

### 架构

```
用户消息
    ↓
文件检测（file_utils.py）
    ↓
图片识别 → base64 编码
    ↓
Vision 工具（vision_tools.py）
    ↓
OpenAI 客户端 → qwen3.5-plus API
    ↓
返回分析结果
```

### 核心文件

- `service/tools/vision_tools.py` - Vision 工具实现
- `service/tools/file_utils.py` - 文件检测和 base64 编码
- `service/tools/legal_tools.py` - 工具注册
- `test_vision_tools.py` - 测试脚本

---

## 🎯 示例场景

### 场景 1: 合同扫描件 OCR

```
📎 附件文件：
D:/contracts/scanned_contract.png

请提取这份合同的所有文字内容，包括条款、签名和日期。
```

### 场景 2: 证据图片分析

```
📎 附件文件：
D:/evidence/photo1.jpg

这张照片拍摄的是什么地点？有哪些人和物体？时间可能是什么时候？
```

### 场景 3: 图表数据提取

```
📎 附件文件：
D:/reports/chart.png

这是一个统计图表，请提取图表中的所有数据和文字说明。
```

---

## 📞 支持

如有问题，请查看：
- 日志文件：`backend/logs/app.log`
- 测试脚本：`test_vision_tools.py`
- 文档：`docs/vision_tools.md`
