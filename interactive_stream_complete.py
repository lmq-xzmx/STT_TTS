import asyncio
import numpy as np
import torch
import json
import os
import time
import pyaudio
import wave
from typing import AsyncGenerator, List, Dict, Any, Optional
from queue import Queue
from threading import Thread

# 导入STT模块
from STT.SenseVoice.utils.stream_processor import StreamProcessor
from STT.SenseVoice.utils.frontend import WavFrontend
from STT.SenseVoice.model import SenseVoiceSmall

# 导入LLM模块
from deepseekV3_api.chat import generate_response

# 音频捕获类
class AudioCapture:
    def __init__(self, callback, sample_rate=16000, chunk_size=1600):
        self.callback = callback
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        
    def start_recording(self):
        """开始录音"""
        self.is_recording = True
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback
        )
        self.stream.start_stream()
        
    def stop_recording(self):
        """停止录音"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.is_recording = False
        
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """音频回调函数"""
        if self.is_recording:
            # 将字节数据转换为numpy数组
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            # 调用回调函数处理音频数据
            asyncio.run_coroutine_threadsafe(self.callback(audio_data), asyncio.get_event_loop())
        return (in_data, pyaudio.paContinue)
        
    def __del__(self):
        """清理资源"""
        self.stop_recording()
        self.p.terminate()

# 音频处理类
class AudioProcessor:
    def __init__(self, sample_rate=16000, chunk_size=1600):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        
        # 初始化前端处理器
        self.frontend = WavFrontend(cmvn_file=None, 
                                    global_cmvn=True, 
                                    feature_extraction_conf=None)
        
        # 初始化流处理器
        self.stream_processor = StreamProcessor(
            frontend=self.frontend,
            sample_rate=sample_rate,
            chunk_size=chunk_size,
            buffer_size=32000  # 2秒缓冲区
        )
        
        # 音频处理类（续）
        
        # 加载SenseVoice模型
        model_dir = "iic/SenseVoiceSmall"  # 请确保模型路径正确
        self.model, self.kwargs = SenseVoiceSmall.from_pretrained(
            model=model_dir, 
            device=os.getenv("SENSEVOICE_DEVICE", "cuda:0")
        )
        self.model.eval()
        
        # 上一次识别的文本，用于增量更新
        self.last_text = ""
        self.accumulated_text = ""
        
    def add_audio_chunk(self, chunk: np.ndarray) -> None:
        """添加音频块到处理器"""
        self.stream_processor.add_chunk(chunk)
        
    async def process_audio(self) -> Optional[str]:
        """处理音频并返回识别结果"""
        # 检查是否有足够的音频数据
        if not self.stream_processor.is_speech_detected():
            return None
            
        # 获取特征
        feat, feat_len = self.stream_processor.get_feature_for_model()
        if len(feat) == 0:
            return None
            
        # 使用模型进行推理
        with torch.no_grad():
            result = self.model.inference(
                data_in=[feat],
                language="auto",  # 自动检测语言
                use_itn=False,
                ban_emo_unk=False,
                key=["stream"],
                fs=self.sample_rate,
                **self.kwargs
            )
            
        if not result or len(result[0]) == 0:
            return None
            
        # 获取识别结果
        text = result[0][0]["text"]
        
        # 如果结果与上次相同，返回None
        if text == self.last_text:
            return None
            
        # 更新上次识别结果
        new_text = text[len(self.last_text):].strip()
        self.last_text = text
        
        # 累积文本
        if new_text:
            self.accumulated_text += new_text + " "
            return new_text
            
        return None
        
    def reset(self):
        """重置处理器状态"""
        self.stream_processor.reset()
        self.last_text = ""
        self.accumulated_text = ""

# LLM处理类
class LLMProcessor:
    def __init__(self):
        # 初始化LLM相关配置
        self.history = []
        self.response_buffer = ""
        
    async def process_text_stream(self, text: str) -> AsyncGenerator[str, None]:
        """流式处理文本并生成回复"""
        # 添加用户消息到历史
        self.history.append({"role": "user", "content": text})
        
        # 调用DeepSeek V3 API进行流式生成
        # 如果函数名是get_streaming_response，请修改这里
        full_response = ""
        async for chunk in generate_response(self.history, stream=True):
            full_response += chunk
            yield chunk
            
        # 添加完整的助手回复到历史
        self.history.append({"role": "assistant", "content": full_response})
        
    def reset(self):
        """重置对话历史"""
        self.history = []

# 主流程控制器
class StreamingAIAssistant:
    def __init__(self):
        self.audio_processor = AudioProcessor()
        self.llm_processor = LLMProcessor()
        
        # 用于在组件之间传递数据的队列
        self.stt_to_llm_queue = asyncio.Queue()
        self.llm_to_tts_queue = asyncio.Queue()
        
        # 控制标志
        self.is_running = False
        self.is_processing = False
        
        # 语音输入捕获
        self.audio_capture = AudioCapture(self.add_audio_data)
        
    async def start(self):
        """启动助手"""
        self.is_running = True
        self.audio_processor.reset()
        self.llm_processor.reset()
        
        # 开始录音
        self.audio_capture.start_recording()
        
        # 启动各个处理任务
        await asyncio.gather(
            self.stt_task(),
            self.llm_task(),
            # self.tts_task()  # TTS任务暂未实现
        )
        
    async def stop(self):
        """停止助手"""
        self.is_running = False
        self.audio_capture.stop_recording()
        
    async def add_audio_data(self, audio_data: np.ndarray):
        """添加音频数据"""
        self.audio_processor.add_audio_chunk(audio_data)
        
    async def stt_task(self):
        """STT处理任务"""
        while self.is_running:
            # 处理音频并获取文本
            text = await self.audio_processor.process_audio()
            
            if text:
                print(f"[STT] 识别到: {text}")
                # 将文本放入队列，传递给LLM
                await self.stt_to_llm_queue.put(text)
                
            # 短暂等待，避免CPU占用过高
            await asyncio.sleep(0.1)
            
    async def llm_task(self):
        """LLM处理任务"""
        accumulated_text = ""
        last_process_time = 0
        
        while self.is_running:
            # 检查是否有新的文本输入
            try:
                # 非阻塞方式获取队列数据
                text = self.stt_to_llm_queue.get_nowait()
                accumulated_text += text + " "
                self.stt_to_llm_queue.task_done()
                
                # 更新最后处理时间
                last_process_time = time.time()
            except asyncio.QueueEmpty:
                # 队列为空，检查是否需要处理累积的文本
                current_time = time.time()
                if accumulated_text and (current_time - last_process_time > 1.0) and not self.is_processing:
                    # 如果有累积的文本且超过1秒没有新输入，开始处理
                    self.is_processing = True
                    print(f"[LLM] 处理文本: {accumulated_text}")
                    
                    # 流式处理文本
                    async for response_chunk in self.llm_processor.process_text_stream(accumulated_text):
                        print(f"[LLM] 生成: {response_chunk}", end="", flush=True)
                        # 将LLM的响应块放入队列，传递给TTS
                        await self.llm_to_tts_queue.put(response_chunk)
                        
                    print()  # 换行
                    # 重置累积文本和处理标志
                    accumulated_text = ""
                    self.is_processing = False
                    
            # 短暂等待，避免CPU占用过高
            await asyncio.sleep(0.1)
    
    async def tts_task(self):
        """TTS处理任务 (待实现)"""
        # 这里将来实现TTS流式处理
        pass

# 用户界面类 (简单的命令行界面)
class CommandLineInterface:
    def __init__(self, assistant):
        self.assistant = assistant
        
    async def run(self):
        """运行命令行界面"""
        print("=== 流式语音交互助手 ===")
        print("按 Enter 开始对话，输入 'q' 退出")
        
        while True:
            cmd = input("> ")
            if cmd.lower() == 'q':
                break
                
            print("开始对话，请说话...")
            await self.assistant.start()
            
            # 等待用户按Enter结束对话
            input("按 Enter 结束对话...")
            await self.assistant.stop()
            
            print("对话结束")

# 主函数
async def main():
    # 创建助手实例
    assistant = StreamingAIAssistant()
    
    # 创建命令行界面
    cli = CommandLineInterface(assistant)
    
    # 运行界面
    await cli.run()

if __name__ == "__main__":
    asyncio.run(main())