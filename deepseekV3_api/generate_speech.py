from pathlib import Path
import os
import time
import shutil
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print("环境变量文件已加载")
else:
    print("警告: 环境变量文件不存在")

# 从环境变量获取API密钥
api_key = None
try:
    with open(dotenv_path, 'r') as f:
        env_content = f.read()
        for line in env_content.split('\n'):
            if line.startswith('OPENAI_API_KEY='):
                api_key = line.split('=', 1)[1].strip()
                print("已从.env文件读取API密钥")
                break
except Exception as e:
    print(f"读取.env文件时出错: {e}")

if not api_key:
    print("错误: 未找到API密钥，请检查.env文件")
    exit(1)

# 创建语音文件存储目录
speech_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "speech_files"
if not speech_dir.exists():
    speech_dir.mkdir(parents=True)
    print(f"已创建语音文件存储目录: {speech_dir}")

# 清理旧的语音文件
def cleanup_speech_files(directory, max_size_gb=1, target_size_mb=200):
    """
    清理旧的语音文件，当目录大小超过max_size_gb时，
    删除最旧的文件直到目录大小小于target_size_mb
    """
    max_size_bytes = max_size_gb * 1024 * 1024 * 1024  # 转换为字节
    target_size_bytes = target_size_mb * 1024 * 1024   # 转换为字节
    
    # 获取目录总大小
    total_size = sum(f.stat().st_size for f in directory.glob('**/*') if f.is_file())
    
    if total_size > max_size_bytes:
        print(f"语音文件夹大小({total_size/1024/1024:.2f}MB)超过限制({max_size_gb}GB)，开始清理...")
        
        # 获取所有mp3文件及其修改时间
        files = [(f, f.stat().st_mtime) for f in directory.glob('*.mp3') if f.is_file()]
        # 按修改时间排序（最旧的在前）
        files.sort(key=lambda x: x[1])
        
        # 删除旧文件直到目录大小小于目标大小
        for file_path, _ in files:
            if total_size <= target_size_bytes:
                break
                
            file_size = file_path.stat().st_size
            print(f"删除文件: {file_path.name} ({file_size/1024/1024:.2f}MB)")
            file_path.unlink()
            total_size -= file_size
        
        print(f"清理完成，当前文件夹大小: {total_size/1024/1024:.2f}MB")

# 在生成新语音前清理旧文件
cleanup_speech_files(speech_dir)

# 生成唯一的文件名（使用时间戳）
timestamp = int(time.time())
speech_file_path = speech_dir / f"xiaoma_speech_{timestamp}.mp3"

# 初始化OpenAI客户端
client = OpenAI(
    api_key=api_key,
    base_url="https://api.siliconflow.cn/v1"
)

# 获取用户输入的文本
user_input = input("请输入要转换为语音的文本: ")

print(f"正在生成语音，使用小马音色...")

# 使用刚才创建的自定义音色
with client.audio.speech.with_streaming_response.create(
    model="FunAudioLLM/CosyVoice2-0.5B",
    voice="speech:xiaoma:4on1q9y2b5:smwvoogtaqejdkgmfxpq",  # 使用刚才创建的音色URI
    input=user_input,
    response_format="mp3"
) as response:
    response.stream_to_file(speech_file_path)

print(f"语音生成成功！文件保存在: {speech_file_path}")