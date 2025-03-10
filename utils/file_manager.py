import os
from pathlib import Path
import time

def get_directory_size(directory):
    """获取目录的总大小（字节）"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def cleanup_speech_files(directory, max_size_mb=200, target_size_mb=60):
    """
    清理旧的语音文件，当目录大小超过max_size_mb时，
    删除最旧的文件直到目录大小小于target_size_mb
    """
    directory = Path(directory)
    max_size_bytes = max_size_mb * 1024 * 1024  # 转换为字节
    target_size_bytes = target_size_mb * 1024 * 1024   # 转换为字节
    
    # 获取目录总大小
    total_size = get_directory_size(directory)
    
    if total_size > max_size_bytes:
        print(f"语音文件夹大小({total_size/1024/1024:.2f}MB)超过限制({max_size_mb}MB)，开始清理...")
        
        # 获取所有mp3文件及其修改时间
        files = []
        for f in directory.glob('**/*.mp3'):
            if f.is_file():
                files.append((f, f.stat().st_mtime))
        
        # 按修改时间排序（最旧的在前）
        files.sort(key=lambda x: x[1])
        
        # 删除旧文件直到目录大小小于目标大小
        deleted_count = 0
        for file_path, mtime in files:
            if total_size <= target_size_bytes:
                break
                
            file_size = file_path.stat().st_size
            mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
            print(f"删除文件: {file_path.name} ({file_size/1024/1024:.2f}MB) - 创建于 {mtime_str}")
            
            file_path.unlink()
            total_size -= file_size
            deleted_count += 1
        
        print(f"清理完成，删除了 {deleted_count} 个文件")
        print(f"当前文件夹大小: {total_size/1024/1024:.2f}MB")
    
    return total_size