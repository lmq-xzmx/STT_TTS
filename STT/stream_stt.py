#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# 基于 SenseVoice 的流式语音识别实现

import os
import time
import numpy as np
import torch
import pyaudio
import threading
import queue
import wave
from pathlib import Path
from model import SenseVoiceSmall
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from utils.stream_processor import StreamProcessor
from utils.frontend import WavFrontend

class StreamingSTT:
    """流式语音识别类"""
    
    def __init__(
        self,
        model_dir="iic/SenseVoiceSmall",
        device=None,
        sample_rate=16000,
        chunk_size=1600,  # 0.1秒的音频
        buffer_size=32000,  # 2秒的缓冲区
        energy_threshold=300,  # 语音检测阈值
        silence_timeout=2.0,  # 静音超时时间(秒)
        language="auto",  # 语言选择
    ):
        # 设置设备
        if device is None:
            device = os.getenv("SENSEVOICE_DEVICE", "cuda:0" if torch.cuda.is_available() else "cpu")
        
        print(f"正在加载模型，使用设备: {device}...")
        # 加载模型
        self.model, self.kwargs = SenseVoiceSmall.from_pretrained(model=model_dir, device=device)
        self.model.eval()
        print("模型加载完成")
        
        # 创建前端处理器
        self.frontend = WavFrontend(
            cmvn_file=f"{self.kwargs['model_path']}/am.mvn",
            fs=sample_rate
        )
        
        # 创建流处理器
        self.stream_processor = StreamProcessor(
            frontend=self.frontend,
            sample_rate=sample_rate,
            chunk_size=chunk_size,
            buffer_size=buffer_size
        )
        
        # 设置参数
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.energy_threshold = energy_threshold
        self.silence_timeout = silence_timeout
        self.language = language
        
        # 状态变量
        self.is_listening = False
        self.last_speech_time = time.time()
        self.current_text = ""
        self.is_speaking = False
        
        # 创建音频队列
        self.audio_queue = queue.Queue()
        
        # 创建结果队列
        self.result_queue = queue.Queue()
        
        # 创建录音目录
        self.recordings_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "recordings"
        if not self.recordings_dir.exists():
            self.recordings_dir.mkdir(parents=True)
            print(f"已创建录音文件存储目录: {self.recordings_dir}")
    
    def start_listening(self):
        """开始监听麦克风输入"""
        if self.is_listening:
            print("已经在监听中")
            return
        
        self.is_listening = True
        self.current_text = ""
        
        # 启动音频处理线程
        self.processing_thread = threading.Thread(target=self._process_audio_stream)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        # 启动麦克风监听线程
        self.listening_thread = threading.Thread(target=self._listen_microphone)
        self.listening_thread.daemon = True
        self.listening_thread.start()
        
        print("开始监听麦克风输入...")
    
    def stop_listening(self):
        """停止监听麦克风输入"""
        if not self.is_listening:
            return
        
        self.is_listening = False
        
        # 等待线程结束
        if hasattr(self, 'listening_thread') and self.listening_thread.is_alive():
            self.listening_thread.join(timeout=1)
        
        if hasattr(self, 'processing_thread') and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1)
        
        # 重置处理器状态
        self.stream_processor.reset()
        print("已停止监听")
    
    def _listen_microphone(self):
        """监听麦克风并将音频数据添加到队列"""
        # 初始化PyAudio
        p = pyaudio.PyAudio()
        
        # 打开音频流
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        # 创建录音文件
        timestamp = int(time.time())
        recording_path = self.recordings_dir / f"recording_{timestamp}.wav"
        wf = wave.open(str(recording_path), 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(self.sample_rate)
        
        print(f"录音文件将保存至: {recording_path}")
        
        try:
            while self.is_listening:
                # 读取音频数据
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                
                # 转换为numpy数组
                audio_data = np.frombuffer(data, dtype=np.float32)
                
                # 添加到队列
                self.audio_queue.put(audio_data)
                
                # 保存到WAV文件 (需要转换为int16格式)
                wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())
                
        finally:
            # 关闭流和PyAudio
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # 关闭录音文件
            wf.close()
            print(f"录音已保存: {recording_path}")
    
    def get_feature_for_model(self):
        """获取用于模型的特征"""
        feat, feat_len = self.stream_processor.process_buffer()
        
        # 转换为torch张量
        if feat.size > 0:
            feat_tensor = torch.from_numpy(feat).unsqueeze(0)
            feat_len_tensor = torch.tensor([feat_len], dtype=torch.int32)
            return feat_tensor, feat_len_tensor
        else:
            return torch.tensor([]), torch.tensor([])
    
    def _process_audio_stream(self):
        """处理音频流并进行识别"""
        silence_start_time = None
        is_speech_detected = False
        
        while self.is_listening:
            try:
                # 从队列获取音频数据
                audio_data = self.audio_queue.get(timeout=0.5)
                
                # 添加到处理器缓冲区
                self.stream_processor.add_chunk(audio_data)
                
                # 检测是否有语音
                if self.stream_processor.is_speech_detected(self.energy_threshold):
                    # 有语音，更新时间戳
                    self.last_speech_time = time.time()
                    silence_start_time = None
                    
                    if not is_speech_detected:
                        print("检测到语音...")
                        is_speech_detected = True
                    
                    # 获取特征并进行识别
                    feat, feat_len = self.get_feature_for_model()
                    
                    if feat.size(0) > 0:
                        # 进行识别
                        with torch.no_grad():
                            result = self.model.inference(
                                data_in=feat,
                                data_len=feat_len,
                                language=self.language,
                                use_itn=False,
                                ban_emo_unk=False,
                                **self.kwargs
                            )
                            
                            if result and len(result[0]) > 0:
                                text = rich_transcription_postprocess(result[0][0]["text"])
                                if text and text != self.current_text:
                                    self.current_text = text
                                    self.result_queue.put(text)
                                    print(f"识别结果: {text}")
                
                else:
                    # 没有语音，检查是否超时
                    if is_speech_detected:
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time > self.silence_timeout:
                            print("检测到静音，结束当前识别")
                            is_speech_detected = False
                            
                            # 最终识别结果
                            if self.current_text:
                                print(f"最终识别结果: {self.current_text}")
                                # 重置当前文本
                                self.current_text = ""
                            
                            # 重置处理器状态，准备下一次识别
                            self.stream_processor.reset()
                
                # 标记任务完成
                self.audio_queue.task_done()
                
            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                print(f"处理音频时出错: {e}")
    
    def get_result(self, timeout=None):
        """获取识别结果"""
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_current_text(self):
        """获取当前识别的文本"""
        return self.current_text

# 如果直接运行此脚本，则执行简单的演示
if __name__ == "__main__":
    print("初始化流式语音识别...")
    
    # 创建流式STT实例
    stt = StreamingSTT()
    
    print("按Enter开始录音，再次按Enter停止...")
    input()
    
    # 开始监听
    stt.start_listening()
    
    print("正在录音和识别，按Enter停止...")
    input()
    
    # 停止监听
    stt.stop_listening()
    
    print("识别结束")