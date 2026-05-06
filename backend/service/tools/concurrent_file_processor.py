"""
并发文件处理工具 - 使用线程池优化大文件并发作业

功能：
1. 多线程并发读取文件
2. 并发解析文档（PDF/DOCX/XLSX/PPTX）
3. 批量处理大文件
4. 进度跟踪和错误处理

使用示例：
    from service.tools.concurrent_file_processor import ConcurrentFileProcessor
    
    # 创建处理器
    processor = ConcurrentFileProcessor(max_workers=5)
    
    # 并发读取多个文件
    results = await processor.process_files(file_paths)
    
    # 或并发解析文档
    results = await processor.parse_documents(doc_paths)
"""
import os
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class FileTask:
    """文件处理任务"""
    file_path: str
    task_type: str  # 'read', 'parse', 'convert'
    params: Dict[str, Any] = None
    priority: int = 0  # 优先级，0 为普通


@dataclass
class FileResult:
    """文件处理结果"""
    file_path: str
    success: bool
    result: Dict[str, Any] = None
    error: Optional[str] = None
    duration: float = 0.0  # 处理耗时（秒）
    file_size: int = 0  # 文件大小（字节）


class ConcurrentFileProcessor:
    """并发文件处理器"""
    
    def __init__(
        self,
        max_workers: int = 5,
        max_file_size: int = 50 * 1024 * 1024,  # 50MB
        timeout_per_file: int = 60,  # 每个文件超时时间（秒）
    ):
        """
        初始化并发文件处理器
        
        Args:
            max_workers: 最大工作线程数
            max_file_size: 最大文件大小（字节）
            timeout_per_file: 每个文件的超时时间（秒）
        """
        self.max_workers = max_workers
        self.max_file_size = max_file_size
        self.timeout_per_file = timeout_per_file
        
        # 线程池
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix='file_processor'
        )
        
        # 进度跟踪
        self.progress = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'current': 0
        }
        
        logger.info(f"✅ 并发文件处理器已初始化 (workers={max_workers}, max_size={max_file_size/1024/1024:.1f}MB)")
    
    def __del__(self):
        """析构时关闭线程池"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
    
    def _check_file(self, file_path: str) -> Dict[str, Any]:
        """
        检查文件是否可处理
        
        Returns:
            Dict: {success, file_size, error}
        """
        path = Path(file_path)
        
        # 检查文件是否存在
        if not path.exists():
            return {
                'success': False,
                'error': f'文件不存在：{file_path}'
            }
        
        # 检查是否是文件
        if not path.is_file():
            return {
                'success': False,
                'error': f'不是文件：{file_path}'
            }
        
        # 检查文件大小
        file_size = path.stat().st_size
        if file_size > self.max_file_size:
            return {
                'success': False,
                'error': f'文件过大 ({file_size/1024/1024:.2f}MB)，最大支持 {self.max_file_size/1024/1024:.1f}MB'
            }
        
        return {
            'success': True,
            'file_size': file_size
        }
    
    def _read_file_sync(self, task: FileTask) -> FileResult:
        """
        同步读取文件（在线程池中执行）
        
        Args:
            task: 文件任务
            
        Returns:
            FileResult: 处理结果
        """
        start_time = time.time()
        
        try:
            # 1. 检查文件
            check_result = self._check_file(task.file_path)
            if not check_result['success']:
                return FileResult(
                    file_path=task.file_path,
                    success=False,
                    error=check_result['error'],
                    duration=time.time() - start_time
                )
            
            file_size = check_result['file_size']
            
            # 2. 导入读取工具
            from service.tools.file_utils import read_file_content
            
            # 3. 读取文件
            params = task.params or {}
            max_chars = params.get('max_chars', 100000)
            
            result = read_file_content(
                file_path=task.file_path,
                max_chars=max_chars
            )
            
            duration = time.time() - start_time
            
            if result.get('success'):
                logger.debug(f"✅ 文件读取成功：{task.file_path} ({duration:.2f}s, {file_size/1024:.1f}KB)")
                return FileResult(
                    file_path=task.file_path,
                    success=True,
                    result=result,
                    duration=duration,
                    file_size=file_size
                )
            else:
                logger.warning(f"⚠️ 文件读取失败：{task.file_path} - {result.get('error')}")
                return FileResult(
                    file_path=task.file_path,
                    success=False,
                    error=result.get('error'),
                    duration=duration,
                    file_size=file_size
                )
                
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ 文件读取异常：{task.file_path} - {e}")
            return FileResult(
                file_path=task.file_path,
                success=False,
                error=str(e),
                duration=duration
            )
    
    def _parse_document_sync(self, task: FileTask) -> FileResult:
        """
        同步解析文档（在线程池中执行）
        
        Args:
            task: 文件任务
            
        Returns:
            FileResult: 处理结果
        """
        start_time = time.time()
        
        try:
            # 1. 检查文件
            check_result = self._check_file(task.file_path)
            if not check_result['success']:
                return FileResult(
                    file_path=task.file_path,
                    success=False,
                    error=check_result['error'],
                    duration=time.time() - start_time
                )
            
            file_size = check_result['file_size']
            
            # 2. 导入文档解析器
            from service.tools.document_parser import parse_document
            
            # 3. 解析文档
            result = parse_document(task.file_path)
            
            duration = time.time() - start_time
            
            if result.get('success'):
                logger.debug(f"✅ 文档解析成功：{task.file_path} ({duration:.2f}s, {file_size/1024:.1f}KB)")
                return FileResult(
                    file_path=task.file_path,
                    success=True,
                    result=result,
                    duration=duration,
                    file_size=file_size
                )
            else:
                logger.warning(f"⚠️ 文档解析失败：{task.file_path} - {result.get('error')}")
                return FileResult(
                    file_path=task.file_path,
                    success=False,
                    error=result.get('error'),
                    duration=duration,
                    file_size=file_size
                )
                
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ 文档解析异常：{task.file_path} - {e}")
            return FileResult(
                file_path=task.file_path,
                success=False,
                error=str(e),
                duration=duration
            )
    
    async def process_files(
        self,
        file_paths: List[str],
        task_type: str = 'read',
        params: Dict[str, Any] = None,
        show_progress: bool = True
    ) -> List[FileResult]:
        """
        并发处理多个文件
        
        Args:
            file_paths: 文件路径列表
            task_type: 任务类型 ('read', 'parse')
            params: 额外参数
            show_progress: 是否显示进度
            
        Returns:
            List[FileResult]: 处理结果列表
        """
        if not file_paths:
            return []
        
        # 初始化进度
        self.progress = {
            'total': len(file_paths),
            'completed': 0,
            'failed': 0,
            'current': 0
        }
        
        logger.info(f"🚀 开始并发处理 {len(file_paths)} 个文件 (workers={self.max_workers})")
        start_time = time.time()
        
        # 创建任务
        tasks = [
            FileTask(
                file_path=path,
                task_type=task_type,
                params=params or {}
            )
            for path in file_paths
        ]
        
        # 在线程池中执行
        loop = asyncio.get_event_loop()
        
        # 提交所有任务到线程池
        futures = []
        for task in tasks:
            if task_type == 'parse':
                future = loop.run_in_executor(
                    self.executor,
                    self._parse_document_sync,
                    task
                )
            else:  # 'read'
                future = loop.run_in_executor(
                    self.executor,
                    self._read_file_sync,
                    task
                )
            futures.append(future)
        
        # 等待所有任务完成
        results = []
        for i, future in enumerate(asyncio.as_completed(futures, timeout=self.timeout_per_file)):
            try:
                result = await future
                results.append(result)
                
                # 更新进度
                if result.success:
                    self.progress['completed'] += 1
                else:
                    self.progress['failed'] += 1
                self.progress['current'] += 1
                
                # 显示进度
                if show_progress:
                    progress_pct = (self.progress['current'] / self.progress['total']) * 100
                    logger.info(f"📊 进度：{self.progress['current']}/{self.progress['total']} ({progress_pct:.1f}%) - 成功：{self.progress['completed']}, 失败：{self.progress['failed']}")
                
            except asyncio.TimeoutError:
                logger.error(f"⏰ 文件处理超时：{file_paths[i]}")
                results.append(FileResult(
                    file_path=file_paths[i],
                    success=False,
                    error='处理超时',
                    duration=self.timeout_per_file
                ))
                self.progress['failed'] += 1
        
        total_duration = time.time() - start_time
        avg_duration = total_duration / len(file_paths) if file_paths else 0
        
        logger.info(f"✅ 并发处理完成：{len(results)} 个文件，总耗时 {total_duration:.2f}s，平均 {avg_duration:.2f}s/文件")
        
        return results
    
    async def process_files_batch(
        self,
        file_paths: List[str],
        batch_size: int = 10,
        task_type: str = 'read',
        params: Dict[str, Any] = None
    ) -> List[FileResult]:
        """
        分批处理大量文件（避免内存溢出）
        
        Args:
            file_paths: 文件路径列表
            batch_size: 每批处理数量
            task_type: 任务类型
            params: 额外参数
            
        Returns:
            List[FileResult]: 处理结果列表
        """
        all_results = []
        total_files = len(file_paths)
        
        logger.info(f"📦 开始分批处理 {total_files} 个文件 (batch_size={batch_size})")
        
        for i in range(0, total_files, batch_size):
            batch = file_paths[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_files + batch_size - 1) // batch_size
            
            logger.info(f"🔄 处理批次 {batch_num}/{total_batches}")
            
            batch_results = await self.process_files(
                batch,
                task_type=task_type,
                params=params,
                show_progress=True
            )
            
            all_results.extend(batch_results)
        
        return all_results
    
    def get_progress(self) -> Dict[str, int]:
        """获取当前进度"""
        return self.progress.copy()
    
    def shutdown(self):
        """关闭处理器"""
        logger.info("🛑 关闭并发文件处理器")
        self.executor.shutdown(wait=False)


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

async def concurrent_read_files(
    file_paths: List[str],
    max_workers: int = 5,
    max_chars: int = 100000
) -> List[Dict[str, Any]]:
    """
    并发读取多个文件（便捷函数）
    
    Args:
        file_paths: 文件路径列表
        max_workers: 最大并发数
        max_chars: 最大读取字符数
        
    Returns:
        List[Dict]: 读取结果列表
    """
    processor = ConcurrentFileProcessor(max_workers=max_workers)
    
    results = await processor.process_files(
        file_paths,
        task_type='read',
        params={'max_chars': max_chars}
    )
    
    # 转换为字典格式
    return [
        {
            'file_path': r.file_path,
            'success': r.success,
            'result': r.result,
            'error': r.error,
            'duration': r.duration,
            'file_size': r.file_size
        }
        for r in results
    ]


async def concurrent_parse_documents(
    doc_paths: List[str],
    max_workers: int = 3
) -> List[Dict[str, Any]]:
    """
    并发解析多个文档（便捷函数）
    
    Args:
        doc_paths: 文档路径列表
        max_workers: 最大并发数
        
    Returns:
        List[Dict]: 解析结果列表
    """
    processor = ConcurrentFileProcessor(max_workers=max_workers)
    
    results = await processor.process_files(
        doc_paths,
        task_type='parse'
    )
    
    return [
        {
            'file_path': r.file_path,
            'success': r.success,
            'result': r.result,
            'error': r.error,
            'duration': r.duration,
            'file_size': r.file_size
        }
        for r in results
    ]


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("="*60)
        print("并发文件处理器测试")
        print("="*60)
        
        # 测试文件列表
        test_files = [
            "D:\\Projects\\Pycharm\\AI_agent\\test.docx",
            # 添加更多测试文件...
        ]
        
        # 测试 1: 并发读取
        print("\n测试 1: 并发读取文件")
        print("-"*60)
        results = await concurrent_read_files(test_files, max_workers=3)
        
        for result in results:
            print(f"文件：{result['file_path']}")
            print(f"  成功：{result['success']}")
            print(f"  耗时：{result['duration']:.2f}s")
            if result['error']:
                print(f"  错误：{result['error']}")
        
        # 测试 2: 使用处理器对象
        print("\n测试 2: 使用处理器对象")
        print("-"*60)
        processor = ConcurrentFileProcessor(max_workers=3)
        
        results = await processor.process_files(
            test_files,
            task_type='read',
            show_progress=True
        )
        
        print(f"\n总结果数：{len(results)}")
        print(f"成功：{sum(1 for r in results if r.success)}")
        print(f"失败：{sum(1 for r in results if not r.success)}")
        
        processor.shutdown()
        
        print("\n" + "="*60)
        print("测试完成")
        print("="*60)
    
    asyncio.run(test())
