import queue
import threading
import time
import numpy as np
import pyaudio
import wave
import os
import speech_recognition as sr
from datetime import datetime
from pathlib import Path

class StreamSTT:
    """简化版的流式语音识别"""
    
    def __init__(self, energy_threshold=4000, pause_threshold=0.8):
        """初始化语音识别器"""
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = energy_threshold  # 能量阈值，用于检测语音
        self.recognizer.pause_threshold = pause_threshold    # 停顿阈值，用于检测语音结束
        
        # 创建录音文件存储目录
        self.recordings_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "recordings"
        if not self.recordings_dir.exists():
            self.recordings_dir.mkdir(parents=True)
        
        # 初始化PyAudio
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        
        # 创建音频队列
        self.audio_queue = queue.Queue()
        
        # 当前识别的文本
        self.current_text = ""
        
        # 控制标志
        self.is_listening = False
        self.listen_thread = None
        self.recognize_thread = None
    
    def start_listening(self):
        """开始监听麦克风输入"""
        if self.is_listening:
            return
        
        self.is_listening = True
        print("开始监听麦克风输入...")
        
        # 启动监听线程
        self.listen_thread = threading.Thread(target=self._listen_microphone)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        
        # 启动识别线程
        self.recognize_thread = threading.Thread(target=self._recognize_speech)
        self.recognize_thread.daemon = True
        self.recognize_thread.start()
    
    def stop_listening(self):
        """停止监听"""
        self.is_listening = False
        
        # 等待线程结束
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=2)
        
        if self.recognize_thread and self.recognize_thread.is_alive():
            self.recognize_thread.join(timeout=2)
        
        # 关闭音频流
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        # 关闭PyAudio
        self.audio.terminate()
        
        print("已停止监听")
    
    def get_text(self):
        """获取当前识别的文本"""
        return self.current_text
    
    def _listen_microphone(self):
        """监听麦克风输入，将音频数据放入队列"""
        # 设置音频参数
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        CHUNK = 1024
        
        # 打开音频流
        self.stream = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        # 生成唯一的录音文件名
        timestamp = int(time.time())
        recording_path = self.recordings_dir / f"recording_{timestamp}.wav"
        print(f"录音文件将保存至: {recording_path}")
        
        # 开始录音
        self.frames = []
        
        try:
            while self.is_listening:
                # 读取音频数据
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                
                # 将数据放入队列
                self.audio_queue.put(data)
                
                # 保存数据用于录音文件
                self.frames.append(data)
        except Exception as e:
            print(f"监听麦克风时出错: {e}")
        finally:
            # 保存录音文件
            if self.frames:
                wf = wave.open(str(recording_path), 'wb')
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(self.frames))
                wf.close()
                print(f"录音已保存: {recording_path}")
    
    def _recognize_speech(self):
        """从音频队列中识别语音"""
        # 设置音频参数
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        # 创建临时WAV文件用于识别
        temp_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "temp"
        if not temp_dir.exists():
            temp_dir.mkdir(parents=True)
        
        # 上次识别的时间
        last_recognition_time = time.time()
        
        # 音频缓冲区
        buffer = []
        
        while self.is_listening:
            try:
                # 从队列获取音频数据
                try:
                    audio_data = self.audio_queue.get(timeout=0.5)
                    buffer.append(audio_data)
                except queue.Empty:
                    continue
                
                # 每隔一段时间进行一次识别
                current_time = time.time()
                if current_time - last_recognition_time > 2.0:  # 每2秒识别一次
                    # 如果缓冲区有足够的数据
                    if buffer:
                        # 创建临时WAV文件
                        temp_file = temp_dir / f"temp_{int(time.time())}.wav"
                        
                        # 将缓冲区数据写入临时文件
                        with wave.open(str(temp_file), 'wb') as wf:
                            wf.setnchannels(CHANNELS)
                            wf.setsampwidth(2)  # 16-bit
                            wf.setframerate(RATE)
                            wf.writeframes(b''.join(buffer))
                        
                        # 使用SpeechRecognition识别
                        try:
                            with sr.AudioFile(str(temp_file)) as source:
                                audio = self.recognizer.record(source)
                                text = self.recognizer.recognize_google(audio, language='zh-CN')
                                
                                # 如果识别成功，更新当前文本
                                if text:
                                    # 累积识别结果
                                    if not self.current_text:
                                        self.current_text = text
                                    else:
                                        # 避免重复添加相同的文本
                                        if text not in self.current_text[-len(text):]:
                                            self.current_text += " " + text
                                    
                                    print(f"识别到: {text}")
                        except sr.UnknownValueError:
                            # 无法识别语音
                            pass
                        except sr.RequestError as e:
                            print(f"语音识别服务错误: {e}")
                        
                        # 删除临时文件
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                        
                        # 清空缓冲区
                        buffer = []
                    
                    # 更新识别时间
                    last_recognition_time = current_time
            
            except Exception as e:
                print(f"识别语音时出错: {e}")