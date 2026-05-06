"""
Vision 工具模块 - 图片分析和 OCR

基于 Hermes Agent vision_tools.py 架构实现，适配百佑 LawyerClaw 的 qwen3.5-plus API
支持功能：
- 图片内容分析
- OCR 文字提取
- 图片描述生成
- 视觉问答

Usage:
    from service.tools.vision_tools import vision_analyze_tool
    import asyncio
    
    # OCR 示例
    result = await vision_analyze_tool(
        image_path="D:/images/document.png",
        prompt="请提取这张图片中的所有文字内容"
    )
    
    # 图片分析示例
    result = await vision_analyze_tool(
        image_path="D:/images/scene.jpg",
        prompt="图中描绘的是什么景象？请详细描述"
    )
"""
import os
import re
import base64
import hashlib
import logging
import uuid
import asyncio
import httpx
from pathlib import Path
from functools import lru_cache
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from openai import AsyncOpenAI
from service.tools.legal_tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
# 可选依赖：Pillow（图片压缩）
# ═══════════════════════════════════════════
try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    logger.warning("Pillow 未安装，图片压缩功能将禁用。运行: pip install Pillow")


# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

# 从环境变量读取 API 配置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://coding.dashscope.aliyuncs.com/v1')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'qwen3.5-plus')

# 支持的图片格式
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

# 最大图片大小（10MB）
MAX_IMAGE_SIZE = 10 * 1024 * 1024

# HTTP 下载超时（秒）
DOWNLOAD_TIMEOUT = 30.0

# 最大重试次数
MAX_RETRIES = 3

# ═══════════════════════════════════════════════════════════
# 性能优化配置
# ═══════════════════════════════════════════════════════════

# 图片最大边长（像素）— 超过此尺寸会自动缩放
MAX_IMAGE_DIMENSION = 2000

# 图片压缩质量（JPEG，1-100）
JPEG_QUALITY = 85

# 缓存过期时间（秒），默认 1 小时
CACHE_TTL = 3600

# 全局单例 AsyncOpenAI 客户端（复用 TCP 连接，避免每次重建）
_global_client: Optional[AsyncOpenAI] = None


def get_vision_client() -> AsyncOpenAI:
    """获取全局单例 AsyncOpenAI 客户端（连接复用）"""
    global _global_client
    if _global_client is None:
        _global_client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            # httpx 连接池配置
            http_client=httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                ),
            ),
        )
    return _global_client


def _compute_image_hash(image_path: str) -> str:
    """基于文件路径 + 修改时间计算缓存 key"""
    p = Path(image_path)
    if p.exists():
        mtime = str(p.stat().st_mtime)
    else:
        mtime = "0"
    return hashlib.md5(f"{image_path}:{mtime}".encode()).hexdigest()[:16]


def _compress_image(image_path: str, max_dim: int = MAX_IMAGE_DIMENSION, quality: int = JPEG_QUALITY) -> str:
    """
    压缩/缩放图片（可选，需要 Pillow）
    
    Returns:
        压缩后的图片路径（可能和原路径相同）
    """
    if not HAS_PILLOW:
        return image_path  # 没有 Pillow，跳过压缩
    
    try:
        path = Path(image_path)
        with Image.open(image_path) as img:
            # 获取原始尺寸
            orig_w, orig_h = img.size
            if orig_w <= max_dim and orig_h <= max_dim:
                return image_path  # 不需要压缩
            
            # 计算缩放比例
            scale = max_dim / max(orig_w, orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            
            # 缩放
            img_resized = img.resize((new_w, new_h), Image.LANCZOS)
            
            # 转换为 RGB（处理 RGBA/P 模式）
            if img_resized.mode in ('RGBA', 'P', 'LA'):
                # 创建白色背景
                background = Image.new('RGB', img_resized.size, (255, 255, 255))
                if img_resized.mode == 'P':
                    img_resized = img_resized.convert('RGBA')
                if img_resized.mode in ('RGBA', 'LA'):
                    background.paste(img_resized, mask=img_resized.split()[-1])
                    img_resized = background
                else:
                    img_resized = img_resized.convert('RGB')
            elif img_resized.mode != 'RGB':
                img_resized = img_resized.convert('RGB')
            
            # 保存到临时文件
            compressed_path = str(path.with_suffix('.compressed.jpg'))
            img_resized.save(compressed_path, 'JPEG', quality=quality, optimize=True)
            
            orig_size = path.stat().st_size
            new_size = Path(compressed_path).stat().st_size
            reduction = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0
            logger.info(f"📐 图片压缩: {orig_w}x{orig_h} → {new_w}x{new_h}, "
                       f"{orig_size/1024:.0f}KB → {new_size/1024:.0f}KB (减少 {reduction:.0f}%)")
            
            return compressed_path
            
    except Exception as e:
        logger.warning(f"图片压缩失败，使用原图: {e}")
        return image_path


async def _image_to_base64_async(image_path: str) -> str:
    """
    异步将图片转换为 base64 编码（不阻塞事件循环）
    """
    def _sync_convert():
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"图片文件不存在：{image_path}")
        
        file_size = path.stat().st_size
        if file_size > MAX_IMAGE_SIZE:
            raise ValueError(f"图片文件过大（{file_size / 1024 / 1024:.2f}MB），最大支持 10MB")
        
        image_data = path.read_bytes()
        encoded = base64.b64encode(image_data).decode('ascii')
        mime_type = _get_mime_type(path)
        return f"data:{mime_type};base64,{encoded}"
    
    # 在线程池中执行，避免阻塞事件循环
    return await asyncio.to_thread(_sync_convert)


def _is_image_file(path: str) -> bool:
    """检查是否为支持的图片文件"""
    return Path(path).suffix.lower() in SUPPORTED_IMAGE_FORMATS


def _is_valid_image_url(url: str) -> bool:
    """
    验证图片 URL 格式
    
    Args:
        url: 要验证的 URL
        
    Returns:
        bool: URL 是否有效
    """
    if not url or not isinstance(url, str):
        return False
    
    # 检查 HTTP/HTTPS
    if not url.startswith(("http://", "https://")):
        return False
    
    # 解析 URL
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return False
        return True
    except Exception:
        return False


def _is_safe_url(url: str) -> bool:
    """
    检查 URL 是否安全（防止 SSRF 攻击）
    阻止访问私有 IP 地址
    
    Args:
        url: 要检查的 URL
        
    Returns:
        bool: URL 是否安全
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            return False
        
        # 阻止私有 IP 地址
        private_ips = [
            '127.', '10.', '192.168.', '172.16.', '172.17.', '172.18.',
            '172.19.', '172.20.', '172.21.', '172.22.', '172.23.',
            '172.24.', '172.25.', '172.26.', '172.27.', '172.28.',
            '172.29.', '172.30.', '172.31.', '169.254.', '0.0.0.0',
            'localhost'
        ]
        
        for prefix in private_ips:
            if hostname.startswith(prefix) or hostname == prefix.rstrip('.'):
                return False
        
        return True
    except Exception:
        return False


async def _download_image(image_url: str, destination: Path) -> Path:
    """
    下载图片到临时目录（带重试机制）
    
    Args:
        image_url: 图片 URL
        destination: 保存路径
        
    Returns:
        Path: 下载的图片路径
        
    Raises:
        Exception: 下载失败时抛出异常
    """
    import asyncio
    
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            # 检查 URL 安全性
            if not _is_safe_url(image_url):
                raise ValueError(f"不安全的 URL（可能访问私有地址）: {image_url}")
            
            # 下载图片
            async with httpx.AsyncClient(
                timeout=DOWNLOAD_TIMEOUT,
                follow_redirects=True
            ) as client:
                response = await client.get(
                    image_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "image/*,*/*;q=0.8",
                    }
                )
                response.raise_for_status()
                destination.write_bytes(response.content)
            
            logger.info(f"✅ 图片下载成功：{destination}")
            return destination
            
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s
                logger.warning(f"图片下载失败（{attempt + 1}/{MAX_RETRIES}）: {str(e)[:50]}")
                logger.warning(f"等待 {wait_time}s 后重试...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"图片下载失败，已达最大重试次数：{str(e)[:100]}")
    
    if last_error:
        raise last_error
    raise RuntimeError("下载未执行")


def _image_to_base64(image_path: str) -> str:
    """
    将图片文件转换为 base64 编码
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        base64 编码的图片字符串
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"图片文件不存在：{image_path}")
    
    # 检查文件大小
    file_size = path.stat().st_size
    if file_size > MAX_IMAGE_SIZE:
        raise ValueError(f"图片文件过大（{file_size / 1024 / 1024:.2f}MB），最大支持 10MB")
    
    # 读取并编码
    image_data = path.read_bytes()
    encoded = base64.b64encode(image_data).decode('ascii')
    
    # 确定 MIME 类型
    mime_type = _get_mime_type(path)
    
    # 创建 data URL
    return f"data:{mime_type};base64,{encoded}"


def _get_mime_type(path: Path) -> str:
    """根据文件扩展名获取 MIME 类型"""
    mime_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
    }
    return mime_map.get(path.suffix.lower(), 'image/jpeg')


# ═══════════════════════════════════════════════════════════
# 分析结果缓存（基于文件 hash + prompt hash）
# ═══════════════════════════════════════════════════════════
_vision_cache: Dict[str, Dict[str, Any]] = {}


async def vision_analyze_tool(
    image_source: str,
    prompt: str = "请详细描述这张图片的内容",
    model: Optional[str] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    分析图片内容（支持 OCR 和图片理解）
    
    Args:
        image_source: 图片源（本地路径 或 HTTP/HTTPS URL）
        prompt: 分析问题或指令
        model: 使用的模型（默认使用配置中的模型）
        use_cache: 是否使用缓存
        
    Returns:
        包含分析结果的字典：
        {
            "success": bool,
            "content": str,  # AI 返回的内容
            "error": str,    # 错误信息（如果有）
            "cached": bool,  # 是否来自缓存
        }
    """
    temp_image_path = None
    compressed_path = None
    should_cleanup = False
    
    try:
        # 判断是 URL 还是本地路径
        if image_source.startswith(("http://", "https://")):
            # URL 图片：下载
            logger.info(f"检测到图片 URL: {image_source[:60]}...")
            
            if not _is_valid_image_url(image_source):
                return {
                    "success": False,
                    "error": f"无效的图片 URL: {image_source}",
                    "cached": False,
                }
            
            # 下载到临时目录
            temp_dir = Path("./temp_vision_images")
            temp_image_path = temp_dir / f"temp_image_{uuid.uuid4()}.jpg"
            
            logger.info(f"开始下载图片到：{temp_image_path}")
            await _download_image(image_source, temp_image_path)
            should_cleanup = True
            image_path = str(temp_image_path)
            
        else:
            # 本地路径
            image_path = image_source
            logger.info(f"使用本地图片：{image_path}")
        
        # 验证文件
        if not os.path.exists(image_path):
            return {
                "success": False,
                "error": f"文件不存在：{image_path}",
                "cached": False,
            }
        
        if not _is_image_file(image_path):
            return {
                "success": False,
                "error": f"不支持的文件格式：{Path(image_path).suffix}",
                "cached": False,
            }
        
        logger.info(f"开始分析图片：{image_path}")
        logger.info(f"Prompt: {prompt[:100]}...")
        
        # ⭐ 性能优化 1：图片压缩（可选，需要 Pillow）
        if os.path.isfile(image_path):
            compressed_path = _compress_image(image_path)
            if compressed_path != image_path:
                logger.info(f"使用压缩后的图片: {compressed_path}")
        
        # ⭐ 性能优化 2：缓存检查
        cache_key = None
        if use_cache and not image_source.startswith(("http://", "https://")):
            image_hash = _compute_image_hash(image_path)
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            cache_key = f"{image_hash}_{prompt_hash}"
            
            if cache_key in _vision_cache:
                cached = _vision_cache[cache_key]
                # 检查缓存是否过期
                import time
                if time.time() - cached.get("_ts", 0) < CACHE_TTL:
                    logger.info(f"✅ 命中缓存（{len(cached['content'])} 字符）")
                    return {
                        "success": True,
                        "content": cached["content"],
                        "usage": cached.get("usage"),
                        "cached": True,
                    }
        
        # ⭐ 性能优化 3：异步 base64 编码
        image_base64 = await _image_to_base64_async(compressed_path or image_path)
        logger.info(f"图片已转换为 base64（长度：{len(image_base64)}）")
        
        # ⭐ 性能优化 4：使用全局单例客户端（连接复用）
        client = get_vision_client()
        
        # 构建多模态消息
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]
        
        # 调用 API
        response = await client.chat.completions.create(
            model=model or OPENAI_MODEL,
            messages=messages,
            max_tokens=4000,  # 增加 token 上限，避免截断
            temperature=0.1,
        )
        
        # 提取结果
        content = response.choices[0].message.content
        
        usage = {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            "total_tokens": response.usage.total_tokens if response.usage else 0,
        }
        
        logger.info(f"图片分析完成（{len(content)} 字符，token: {usage['total_tokens']}）")
        
        # ⭐ 写入缓存
        if cache_key and content:
            import time
            _vision_cache[cache_key] = {
                "content": content,
                "usage": usage,
                "_ts": time.time(),
            }
            # 定期清理过期缓存（简单策略：超过 100 条时清空）
            if len(_vision_cache) > 100:
                _vision_cache.clear()
                logger.info("🧹 缓存已清理（超过容量上限）")
        
        return {
            "success": True,
            "content": content,
            "usage": usage,
            "cached": False,
        }
        
    except Exception as e:
        logger.error(f"图片分析失败：{e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "cached": False,
        }
    
    finally:
        # 清理临时文件（仅 URL 下载的图片）
        if should_cleanup and temp_image_path and temp_image_path.exists():
            try:
                temp_image_path.unlink()
                logger.debug(f"已清理临时文件：{temp_image_path}")
            except Exception as cleanup_error:
                logger.warning(f"清理临时文件失败：{cleanup_error}")
        
        # 清理压缩后的临时文件
        if compressed_path and compressed_path != image_path and os.path.exists(compressed_path):
            try:
                os.unlink(compressed_path)
                logger.debug(f"已清理压缩文件：{compressed_path}")
            except Exception as cleanup_error:
                logger.warning(f"清理压缩文件失败：{cleanup_error}")


async def ocr_tool(
    image_source: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    OCR 文字提取（专用工具）
    
    Args:
        image_source: 图片源（本地路径 或 HTTP/HTTPS URL）
        model: 使用的模型
        
    Returns:
        OCR 结果字典
    """
    # 使用专门的 OCR prompt
    ocr_prompt = """请提取这张图片中的所有可见文字内容。

要求：
1. 按从上到下、从左到右的顺序提取
2. 保持原有的段落和换行格式
3. 如果是表格，尽量保持表格结构
4. 如果是手写文字，尽最大努力识别
5. 如果某些文字不清晰，用 [?] 标记

请直接输出识别到的文字内容，不要添加额外说明。"""
    
    return await vision_analyze_tool(
        image_source=image_source,
        prompt=ocr_prompt,
        model=model
    )


# ═══════════════════════════════════════════════════════════
# Tool 注册
# ═══════════════════════════════════════════════════════════

class VisionAnalyzeTool(BaseTool):
    """图片分析工具"""
    
    name = "vision_analyze"
    description = "分析图片内容，支持 OCR 文字提取、图片描述、视觉问答等任务"
    
    parameters = {
        "type": "object",
        "properties": {
            "image_source": {
                "type": "string",
                "description": "图片源（本地文件路径 或 HTTP/HTTPS URL），例如：'D:/images/doc.png' 或 'https://example.com/image.jpg'"
            },
            "prompt": {
                "type": "string",
                "description": "分析问题或指令，例如：'图中有什么文字？'、'描述这张图片'、'这是什么类型的文档？'"
            }
        },
        "required": ["image_source", "prompt"]
    }
    
    async def execute(self, image_source: str, prompt: str = "请描述这张图片") -> ToolResult:
        """执行图片分析"""
        result = await vision_analyze_tool(image_source, prompt)
        
        if result["success"]:
            return ToolResult(
                success=True,
                content=result["content"],
                data=result.get("usage")
            )
        else:
            return ToolResult(
                success=False,
                content="",
                error=result.get("error", "未知错误")
            )


class OCRTool(BaseTool):
    """OCR 文字提取工具"""
    
    name = "ocr_extract"
    description = "从图片中提取文字内容（OCR），支持打印体和手写体识别，支持本地文件和 HTTP/HTTPS URL"
    
    parameters = {
        "type": "object",
        "properties": {
            "image_source": {
                "type": "string",
                "description": "图片源（本地文件路径 或 HTTP/HTTPS URL），例如：'D:/images/doc.png' 或 'https://example.com/image.jpg'"
            }
        },
        "required": ["image_source"]
    }
    
    async def execute(self, image_source: str) -> ToolResult:
        """执行 OCR"""
        result = await ocr_tool(image_source)
        
        if result["success"]:
            return ToolResult(
                success=True,
                content=result["content"]
            )
        else:
            return ToolResult(
                success=False,
                content="",
                error=result.get("error", "未知错误")
            )


# ═══════════════════════════════════════════════════════════
# 工具注册函数
# ═══════════════════════════════════════════════════════════

def register_vision_tools(registry):
    """注册 Vision 工具到工具注册表"""
    registry.register(VisionAnalyzeTool())
    registry.register(OCRTool())
    logger.info("✅ Vision 工具已注册（vision_analyze, ocr_extract）")


# ═══════════════════════════════════════════════════════════
# 测试代码
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    
    async def test_vision():
        """测试 Vision 工具"""
        print("👁️ Vision 工具测试")
        print("=" * 50)
        
        # 测试图片路径（请替换为实际图片）
        test_image = "D:/test_image.png"
        
        if not os.path.exists(test_image):
            print(f"⚠️  测试图片不存在：{test_image}")
            print("请修改 test_image 变量为一个实际存在的图片路径")
            return
        
        # 测试 1: OCR
        print("\n[测试 1] OCR 文字提取")
        result = await ocr_tool(test_image)
        if result["success"]:
            print(f"✅ OCR 成功:\n{result['content'][:500]}")
        else:
            print(f"❌ OCR 失败：{result.get('error')}")
        
        # 测试 2: 图片分析
        print("\n[测试 2] 图片内容分析")
        result = await vision_analyze_tool(
            test_image,
            prompt="图中描绘的是什么景象？请详细描述"
        )
        if result["success"]:
            print(f"✅ 分析成功:\n{result['content'][:500]}")
        else:
            print(f"❌ 分析失败：{result.get('error')}")
    
    asyncio.run(test_vision())
