"""
同步文件处理器 - 用于 Flask 同步环境

在 Flask 的同步视图中使用线程池并发处理文件
"""
import logging
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def read_file_sync(file_path: str, max_chars: int = 100000) -> Dict[str, Any]:
    """
    同步读取单个文件
    
    Args:
        file_path: 文件路径
        max_chars: 最大读取字符数
        
    Returns:
        Dict: 读取结果
    """
    start_time = time.time()
    
    try:
        from service.tools.file_utils import read_file_content
        
        result = read_file_content(file_path, max_chars=max_chars)
        
        duration = time.time() - start_time
        
        if result.get('success'):
            logger.debug(f"✅ 文件读取成功：{file_path} ({duration:.2f}s)")
            return {
                'success': True,
                'result': result,
                'duration': duration,
                'file_path': file_path
            }
        else:
            logger.warning(f"⚠️ 文件读取失败：{file_path} - {result.get('error')}")
            return {
                'success': False,
                'error': result.get('error'),
                'duration': duration,
                'file_path': file_path
            }
            
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ 文件读取异常：{file_path} - {e}")
        return {
            'success': False,
            'error': str(e),
            'duration': duration,
            'file_path': file_path
        }


def process_files_concurrent(
    file_paths: List[str],
    max_workers: int = 5,
    max_chars: int = 100000
) -> List[Dict[str, Any]]:
    """
    并发处理多个文件（同步版本）
    
    Args:
        file_paths: 文件路径列表
        max_workers: 最大并发数
        max_chars: 最大读取字符数
        
    Returns:
        List[Dict]: 处理结果列表
    """
    if not file_paths:
        return []
    
    logger.info(f"🚀 开始并发处理 {len(file_paths)} 个文件 (workers={max_workers})")
    start_time = time.time()
    
    results = []
    
    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_path = {
            executor.submit(read_file_sync, path, max_chars): path
            for path in file_paths
        }
        
        # 收集结果
        completed = 0
        failed = 0
        
        for future in as_completed(future_to_path):
            file_path = future_to_path[future]
            try:
                result = future.result()
                results.append(result)
                
                if result['success']:
                    completed += 1
                else:
                    failed += 1
                
                # 显示进度
                progress_pct = (len(results) / len(file_paths)) * 100
                logger.info(f"📊 进度：{len(results)}/{len(file_paths)} ({progress_pct:.1f}%) - 成功：{completed}, 失败：{failed}")
                
            except Exception as e:
                logger.error(f"❌ 文件处理异常：{file_path} - {e}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'file_path': file_path
                })
                failed += 1
    
    total_duration = time.time() - start_time
    avg_duration = total_duration / len(file_paths) if file_paths else 0
    
    logger.info(f"✅ 并发处理完成：{len(results)} 个文件，总耗时 {total_duration:.2f}s，平均 {avg_duration:.2f}s/文件")
    
    return results


def process_files_smart(
    file_paths: List[str],
    max_chars_map: Dict[str, int] = None
) -> List[Dict[str, Any]]:
    """
    智能处理文件（根据文件类型自动调整参数）
    
    Args:
        file_paths: 文件路径列表
        max_chars_map: 文件类型对应的 max_chars 映射
        
    Returns:
        List[Dict]: 处理结果列表
    """
    if not file_paths:
        return []
    
    # 默认配置
    if max_chars_map is None:
        max_chars_map = {
            '.png': 500000,
            '.jpg': 500000,
            '.jpeg': 500000,
            '.gif': 500000,
            '.webp': 500000,
            '.pdf': 200000,
            '.docx': 200000,
            '.pptx': 200000,
            '.xlsx': 200000,
        }
    
    # 根据文件数量决定并发策略
    if len(file_paths) >= 3:
        # 多个文件：并发处理
        max_workers = min(5, len(file_paths))
        logger.info(f"🚀 使用线程池并发处理 {len(file_paths)} 个文件 (workers={max_workers})")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 为每个文件提交任务
            future_to_path = {}
            for path in file_paths:
                ext = Path(path).suffix.lower()
                max_chars = max_chars_map.get(ext, 100000)
                future = executor.submit(read_file_sync, path, max_chars)
                future_to_path[future] = path
            
            # 收集结果
            for future in as_completed(future_to_path):
                result = future.result()
                results.append(result)
        
        return results
    
    else:
        # 少量文件：顺序处理
        logger.info(f"📖 顺序处理 {len(file_paths)} 个文件")
        results = []
        
        for path in file_paths:
            ext = Path(path).suffix.lower()
            max_chars = max_chars_map.get(ext, 100000)
            result = read_file_sync(path, max_chars)
            results.append(result)
        
        return results
