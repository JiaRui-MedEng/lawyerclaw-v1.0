"""
百佑 LawyerClaw 文件操作系统

基于 Hermes 安全架构实现:
1. 文件读取/写入/修改工具
2. 危险操作检测 (基于 approval.py)
3. 工作空间管理
4. 前端文件选择集成

作者：Hermes Agent 架构迁移
日期：2026 年 1 月
"""
import os
import re
import json
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from service.security.approval_enhanced import check_command_approval, approval_manager
from service.security.skills_guard_enhanced import scan_skill, should_allow_install
from service.models.database import db, SecurityAuditLog

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 文件操作工具
# ═══════════════════════════════════════════════════════════

class FileOperationTool:
    """
    文件操作工具集
    
    功能:
    - 读取文件内容
    - 写入/修改文件
    - 删除文件
    - 创建目录
    - 列出目录内容
    - 安全扫描
    """
    
    name = "file_operation"
    description = "操作本地文件系统，支持读取、写入、修改、删除文件。所有危险操作需要用户审批。"
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "write", "patch", "delete", "mkdir", "list"],
                "description": "操作类型"
            },
            "file_path": {
                "type": "string",
                "description": "文件路径 (相对于工作空间根目录)"
            },
            "content": {
                "type": "string",
                "description": "文件内容 (用于 write/patch)"
            },
            "old_string": {
                "type": "string",
                "description": "要查找的文本 (用于 patch)"
            },
            "new_string": {
                "type": "string",
                "description": "替换文本 (用于 patch)"
            }
        },
        "required": ["action", "file_path"]
    }
    
    def __init__(self, workspace_root: str = None):
        """
        初始化文件操作工具
        
        Args:
            workspace_root: 工作空间根目录
        """
        self.workspace_root = Path(workspace_root).expanduser() if workspace_root else None
        self._lock = __import__('threading').Lock()
    
    def set_workspace(self, workspace_root: str):
        """设置工作空间根目录"""
        self.workspace_root = Path(workspace_root).expanduser()
        logger.info(f"工作空间已设置：{self.workspace_root}")
    
    def _resolve_path(self, file_path: str) -> Path:
        """
        解析文件路径 (确保在工作空间内)
        
        Args:
            file_path: 相对路径或绝对路径
            
        Returns:
            Path: 解析后的绝对路径
            
        Raises:
            ValueError: 路径超出工作空间边界
        """
        path = Path(file_path)
        
        # 如果是绝对路径，检查是否在工作空间内
        if path.is_absolute():
            try:
                resolved = path.resolve()
                if self.workspace_root and not str(resolved).startswith(str(self.workspace_root)):
                    raise ValueError(f"文件路径超出工作空间边界：{file_path}")
                return resolved
            except Exception as e:
                raise ValueError(f"无效的文件路径：{file_path} - {e}")
        
        # 如果是相对路径，相对于工作空间解析
        if self.workspace_root:
            resolved = (self.workspace_root / path).resolve()
            # 安全检查：确保解析后的路径仍在工作空间内
            if not str(resolved).startswith(str(self.workspace_root)):
                raise ValueError(f"文件路径超出工作空间边界：{file_path}")
            return resolved
        
        # 没有工作空间设置，使用绝对路径
        return path.resolve()
    
    def read_file(self, file_path: str, limit: int = 10000) -> Dict[str, Any]:
        """
        读取文件内容
        
        Args:
            file_path: 文件路径
            limit: 最大读取字符数
            
        Returns:
            Dict: {success, content, error, file_info}
        """
        try:
            path = self._resolve_path(file_path)
            
            if not path.exists():
                return {
                    "success": False,
                    "error": f"文件不存在：{file_path}",
                    "file_path": str(path)
                }
            
            if not path.is_file():
                return {
                    "success": False,
                    "error": f"不是文件：{file_path}",
                    "file_path": str(path)
                }
            
            # 检查文件扩展名，判断是否为文档文件
            ext = path.suffix.lower()
            document_extensions = {'.docx', '.pdf', '.pptx', '.xlsx', '.doc', '.ppt'}
            
            # 文档文件使用专用解析器
            if ext in document_extensions:
                from service.tools.file_reader_enhanced import read_any_file
                result = read_any_file(str(path), max_chars=limit)
                self._log_audit("file_read", str(path), "allowed")
                return result
            
            # 检查文件大小
            file_size = path.stat().st_size
            if file_size > limit * 10:  # 10 倍限制
                return {
                    "success": False,
                    "error": f"文件过大 ({file_size} 字节)，最大支持 {limit * 10} 字节",
                    "file_path": str(path)
                }
            
            # 读取文本内容
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read(limit)
            
            # 记录审计日志
            self._log_audit("file_read", str(path), "allowed")
            
            return {
                "success": True,
                "content": content,
                "file_path": str(path),
                "file_info": {
                    "size": file_size,
                    "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    "truncated": file_size > limit
                }
            }
            
        except Exception as e:
            logger.error(f"读取文件失败：{e}")
            self._log_audit("file_read", str(path) if 'path' in locals() else file_path, "error", str(e))
            return {
                "success": False,
                "error": f"读取失败：{e}",
                "file_path": file_path
            }
    
    def write_file(self, file_path: str, content: str, session_id: str = None) -> Dict[str, Any]:
        """
        写入文件内容 (带安全审批)
        
        Args:
            file_path: 文件路径
            content: 文件内容
            session_id: 会话 ID (用于审批)
            
        Returns:
            Dict: {success, error, file_path, requires_approval}
        """
        try:
            path = self._resolve_path(file_path)
            
            # 检查危险操作
            check_result = self._check_dangerous_write(str(path), content)
            
            if check_result.get("requires_approval"):
                return {
                    "success": False,
                    "requires_approval": True,
                    "approval_info": check_result,
                    "file_path": str(path),
                    "content": content
                }
            
            # 执行写入
            return self._execute_write(path, content, session_id)
            
        except Exception as e:
            logger.error(f"写入文件失败：{e}")
            return {
                "success": False,
                "error": f"写入失败：{e}",
                "file_path": file_path
            }
    
    def _check_dangerous_write(self, file_path: str, content: str) -> Dict:
        """检查写入操作是否危险"""
        # 检查危险文件类型
        dangerous_extensions = {'.exe', '.dll', '.so', '.sh', '.bat', '.cmd'}
        path = Path(file_path)
        
        if path.suffix.lower() in dangerous_extensions:
            return {
                "requires_approval": True,
                "pattern_key": "dangerous_file_type",
                "severity": "high",
                "description": f"写入可执行文件类型：{path.suffix}"
            }
        
        # 检查内容中的危险模式
        dangerous_patterns = [
            (r'rm\s+-rf', "recursive delete command"),
            (r'chmod\s+777', "world-writable permissions"),
            (r'curl.*\|.*sh', "pipe to shell"),
            (r'os\.system\s*\(', "system command execution"),
            (r'eval\s*\(', "eval execution"),
            (r'__import__\s*\(', "dynamic import"),
        ]
        
        for pattern, description in dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return {
                    "requires_approval": True,
                    "pattern_key": description,
                    "severity": "high",
                    "description": f"检测到危险代码模式：{description}"
                }
        
        return {"requires_approval": False}
    
    def _execute_write(self, path: Path, content: str, session_id: str = None) -> Dict[str, Any]:
        """执行文件写入 (原子操作)"""
        with self._lock:
            try:
                # 确保目录存在
                path.parent.mkdir(parents=True, exist_ok=True)
                
                # 原子写入 (tempfile + rename)
                fd, tmp_path = tempfile.mkstemp(
                    dir=str(path.parent),
                    prefix=f".{path.name}.tmp.",
                    suffix=""
                )
                
                try:
                    with os.fdopen(fd, 'w', encoding='utf-8') as f:
                        f.write(content)
                        f.flush()
                        os.fsync(f.fileno())
                    
                    # 备份原文件 (如果存在)
                    backup_path = None
                    if path.exists():
                        backup_path = str(path) + ".backup"
                        shutil.copy2(path, backup_path)
                    
                    # 原子替换
                    os.replace(tmp_path, str(path))
                    
                    # 记录审计日志
                    self._log_audit("file_write", str(path), "allowed", session_id=session_id)
                    
                    return {
                        "success": True,
                        "file_path": str(path),
                        "backup_path": backup_path,
                        "message": "文件已写入"
                    }
                    
                except Exception:
                    # 清理临时文件
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    raise
                    
            except Exception as e:
                logger.error(f"写入文件失败：{e}")
                self._log_audit("file_write", str(path), "error", str(e))
                return {
                    "success": False,
                    "error": f"写入失败：{e}",
                    "file_path": str(path)
                }
    
    def patch_file(self, file_path: str, old_string: str, new_string: str,
                   session_id: str = None) -> Dict[str, Any]:
        """
        修补文件内容 (查找替换)
        
        Args:
            file_path: 文件路径
            old_string: 要查找的文本
            new_string: 替换文本
            session_id: 会话 ID
            
        Returns:
            Dict: 操作结果
        """
        try:
            path = self._resolve_path(file_path)
            
            if not path.exists():
                return {
                    "success": False,
                    "error": f"文件不存在：{file_path}"
                }
            
            # 读取原内容
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找匹配
            if old_string not in content:
                # 尝试模糊匹配
                matches = self._fuzzy_find(content, old_string)
                if not matches:
                    return {
                        "success": False,
                        "error": f"未找到匹配的文本：'{old_string[:50]}...'",
                        "suggestions": self._get_similar_strings(content, old_string)
                    }
                # 使用第一个匹配
                old_string = matches[0]
            
            # 执行替换
            new_content = content.replace(old_string, new_string, 1)
            
            # 写入新内容
            return self._execute_write(path, new_content, session_id)
            
        except Exception as e:
            logger.error(f"修补文件失败：{e}")
            return {
                "success": False,
                "error": f"修补失败：{e}",
                "file_path": file_path
            }
    
    def delete_file(self, file_path: str, session_id: str = None) -> Dict[str, Any]:
        """
        删除文件 (带安全审批)
        
        Args:
            file_path: 文件路径
            session_id: 会话 ID
            
        Returns:
            Dict: 操作结果
        """
        try:
            path = self._resolve_path(file_path)
            
            if not path.exists():
                return {
                    "success": False,
                    "error": f"文件不存在：{file_path}"
                }
            
            # 检查危险删除
            check_result = self._check_dangerous_delete(str(path))
            
            if check_result.get("requires_approval"):
                return {
                    "success": False,
                    "requires_approval": True,
                    "approval_info": check_result,
                    "file_path": str(path)
                }
            
            # 执行删除
            if path.is_file():
                # 备份
                backup_path = str(path) + ".backup"
                shutil.copy2(path, backup_path)
                path.unlink()
            elif path.is_dir():
                # 目录删除需要额外审批
                return {
                    "success": False,
                    "requires_approval": True,
                    "approval_info": {
                        "pattern_key": "delete_directory",
                        "severity": "high",
                        "description": f"删除目录：{path}"
                    },
                    "file_path": str(path)
                }
            
            self._log_audit("file_delete", str(path), "allowed", session_id=session_id)
            
            return {
                "success": True,
                "file_path": str(path),
                "backup_path": backup_path if path.is_file() else None,
                "message": "文件已删除"
            }
            
        except Exception as e:
            logger.error(f"删除文件失败：{e}")
            return {
                "success": False,
                "error": f"删除失败：{e}",
                "file_path": file_path
            }
    
    def _check_dangerous_delete(self, file_path: str) -> Dict:
        """检查删除操作是否危险"""
        path = Path(file_path)
        
        # 检查危险路径
        dangerous_paths = [
            '/', '/home', '/etc', '/usr', '/var', '/bin', '/sbin',
            'C:\\', 'C:\\Windows', 'C:\\Program Files'
        ]
        
        for dangerous in dangerous_paths:
            if str(path).startswith(dangerous):
                return {
                    "requires_approval": True,
                    "pattern_key": "delete_system_path",
                    "severity": "critical",
                    "description": f"尝试删除系统路径：{dangerous}"
                }
        
        # 检查重要文件
        important_files = ['.git', '.env', 'config.py', 'settings.py']
        if path.name in important_files:
            return {
                "requires_approval": True,
                "pattern_key": "delete_important_file",
                "severity": "high",
                "description": f"删除重要文件：{path.name}"
            }
        
        return {"requires_approval": False}
    
    def list_directory(self, dir_path: str = ".") -> Dict[str, Any]:
        """
        列出目录内容
        
        Args:
            dir_path: 目录路径
            
        Returns:
            Dict: 目录内容列表
        """
        try:
            path = self._resolve_path(dir_path)
            
            if not path.exists():
                return {
                    "success": False,
                    "error": f"目录不存在：{dir_path}"
                }
            
            if not path.is_dir():
                return {
                    "success": False,
                    "error": f"不是目录：{dir_path}"
                }
            
            items = []
            for item in sorted(path.iterdir()):
                item_info = {
                    "name": item.name,
                    "path": str(item.relative_to(path)) if self.workspace_root else str(item),
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None,
                    "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                }
                items.append(item_info)
            
            return {
                "success": True,
                "directory": str(path),
                "items": items,
                "count": len(items)
            }
            
        except Exception as e:
            logger.error(f"列出目录失败：{e}")
            return {
                "success": False,
                "error": f"列出目录失败：{e}",
                "directory": dir_path
            }
    
    def create_directory(self, dir_path: str, session_id: str = None) -> Dict[str, Any]:
        """
        创建目录
        
        Args:
            dir_path: 目录路径
            session_id: 会话 ID
            
        Returns:
            Dict: 操作结果
        """
        try:
            path = self._resolve_path(dir_path)
            path.mkdir(parents=True, exist_ok=True)
            
            self._log_audit("mkdir", str(path), "allowed", session_id=session_id)
            
            return {
                "success": True,
                "directory": str(path),
                "message": "目录已创建"
            }
            
        except Exception as e:
            logger.error(f"创建目录失败：{e}")
            return {
                "success": False,
                "error": f"创建失败：{e}",
                "directory": dir_path
            }
    
    def _fuzzy_find(self, content: str, pattern: str) -> List[str]:
        """模糊查找匹配项"""
        matches = []
        
        # 精确匹配
        if pattern in content:
            matches.append(pattern)
        
        # 忽略大小写
        if pattern.lower() in content.lower():
            start = content.lower().find(pattern.lower())
            end = start + len(pattern)
            matches.append(content[start:end])
        
        return list(set(matches))
    
    def _get_similar_strings(self, content: str, pattern: str, limit: int = 3) -> List[str]:
        """获取相似字符串"""
        sentences = re.split(r'[.!?]', content)
        similar = []
        
        pattern_words = set(pattern.lower().split())
        
        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            if len(pattern_words & sentence_words) >= 2:
                similar.append(sentence.strip()[:100])
                if len(similar) >= limit:
                    break
        
        return similar
    
    def _log_audit(self, action: str, target: str, result: str, 
                   details: str = None, session_id: str = None):
        """记录审计日志"""
        try:
            audit_log = SecurityAuditLog(
                session_id=session_id,
                audit_type='file_operation',
                action=action,
                target=target,
                result=result,
                details={"details": details} if details else None
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            logger.error(f"审计日志记录失败：{e}")


# 全局实例
file_tool = FileOperationTool()
