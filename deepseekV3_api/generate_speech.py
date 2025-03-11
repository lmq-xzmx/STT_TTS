from pathlib import Path
import os
import time
import shutil
import io
import tempfile
from dotenv import load_dotenv
from openai import OpenAI
import pygame  # 用于音频播放
import threading
import queue

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

# 初始化pygame音频系统 - 使用更高的采样率和缓冲区大小
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)

# 创建一个队列用于存储音频块
audio_queue = queue.Queue()
# 标记是否继续播放
playing = True
# 添加音频块大小参数，较大的块可以减少断句问题
CHUNK_SIZE = 8192  # 增大音频块大小

def play_audio_chunks():
    """从队列中获取音频块并播放"""
    global playing
    
    # 创建临时文件用于存储当前音频块
    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, "temp_chunk.mp3")
    
    # 添加音频缓冲区，用于平滑过渡
    buffer_chunks = []
    buffer_size = 4  # 缓冲3个块再开始播放，减少断句
    
    try:
        while playing:
            try:
                # 非阻塞方式获取音频块，超时1秒
                chunk = audio_queue.get(timeout=1)
                
                # 将音频块添加到缓冲区
                buffer_chunks.append(chunk)
                
                # 当缓冲区达到指定大小或队列为空且有缓冲数据时播放
                if len(buffer_chunks) >= buffer_size or (audio_queue.empty() and buffer_chunks):
                    # 合并缓冲区中的所有块
                    combined_chunk = b''.join(buffer_chunks)
                    buffer_chunks = []
                    
                    # 将合并后的音频块写入临时文件
                    with open(temp_file, 'wb') as f:
                        f.write(combined_chunk)
                    
                    # 加载并播放音频
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    
                    # 等待播放完成，但设置较短的检查间隔
                    while pygame.mixer.music.get_busy():
                        pygame.time.wait(50)  # 减少等待时间，提高响应性
                
                # 标记任务完成
                audio_queue.task_done()
            except queue.Empty:
                # 队列为空，播放剩余缓冲区内容
                if buffer_chunks:
                    combined_chunk = b''.join(buffer_chunks)
                    buffer_chunks = []
                    
                    with open(temp_file, 'wb') as f:
                        f.write(combined_chunk)
                    
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy():
                        pygame.time.wait(50)
                # 继续等待
                continue
    finally:
        # 清理临时文件和目录
        try:
            os.remove(temp_file)
            os.rmdir(temp_dir)
        except:
            pass

def stream_and_play_speech(text, voice_id="speech:xiaoma:4on1q9y2b5:smwvoogtaqejdkgmfxpq", model="FunAudioLLM/CosyVoice2-0.5B"):
    """流式生成语音并同时播放"""
    global playing
    
    # 初始化OpenAI客户端
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.siliconflow.cn/v1"
    )
    
    # 生成唯一的文件名（使用时间戳）
    timestamp = int(time.time())
    speech_file_path = speech_dir / f"xiaoma_speech_{timestamp}.mp3"
    
    # 创建一个内存缓冲区用于存储完整的音频
    full_audio = io.BytesIO()
    
    # 启动播放线程
    playing = True
    play_thread = threading.Thread(target=play_audio_chunks)
    play_thread.daemon = True
    play_thread.start()
    
    try:
        print(f"正在流式生成并播放语音，使用音色ID: {voice_id}...")
        
        # 预处理文本，添加适当的停顿标记
        processed_text = preprocess_text(text)
        
        # 使用流式响应
        with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice_id,
            input=processed_text,
            response_format="mp3",
            speed=0.9,  # 稍微降低语速，提高清晰度
            # 如果API支持以下参数，可以尝试添加
            # clarity=1.2,  # 增加清晰度
            # stability=0.7,  # 保持一定的稳定性
        ) as response:
            # 读取响应流，使用更大的块大小
            for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                if chunk:
                    # 将音频块添加到队列
                    audio_queue.put(chunk)
                    
                    # 同时保存到完整音频
                    full_audio.write(chunk)
        
        # 等待所有音频块播放完成
        audio_queue.join()
        
        # 保存完整的音频文件
        with open(speech_file_path, 'wb') as f:
            f.write(full_audio.getvalue())
        
        print(f"语音生成并播放完成！文件保存在: {speech_file_path}")
        return str(speech_file_path)
    
    except Exception as e:
        print(f"生成或播放语音时出错: {e}")
        return None
    
    finally:
        # 停止播放线程
        playing = False
        if play_thread.is_alive():
            play_thread.join(timeout=2)

def preprocess_text(text):
    """
    预处理文本，添加适当的停顿标记，优化语音生成效果
    """
    import re
    
    # 替换常见标点为更明确的停顿
    text = re.sub(r'([，。！？；：])', r'\1 ', text)
    
    # 在长句子中添加适当的停顿
    sentences = re.split(r'([。！？])', text)
    processed_sentences = []
    
    for i in range(0, len(sentences), 2):
        if i+1 < len(sentences):
            sentence = sentences[i] + sentences[i+1]
        else:
            sentence = sentences[i]
            
        # 对于长句子，在逗号处添加更明显的停顿
        if len(sentence) > 20:
            parts = re.split(r'([，、])', sentence)
            for j in range(0, len(parts), 2):
                if j+1 < len(parts):
                    processed_sentences.append(parts[j] + parts[j+1])
                else:
                    processed_sentences.append(parts[j])
        else:
            processed_sentences.append(sentence)
    
    return ' '.join(processed_sentences)

# 在生成新语音前清理旧文件
cleanup_speech_files(speech_dir)

if __name__ == "__main__":
    # 获取用户输入的文本
    user_input = input("请输入要转换为语音的文本: ")
    
    # 流式生成并播放语音
    stream_and_play_speech(user_input)