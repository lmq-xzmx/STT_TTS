#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
小马过河交互舞台
- 显示视频
- 监听麦克风输入
- 检测唤醒词并激活对应角色
"""

# 在导入部分添加播放音频所需的库
import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import cv2
from PIL import Image, ImageTk
import pyaudio
import numpy as np
import wave
import speech_recognition as sr
import re
import pygame  # 添加pygame用于播放音频

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from deepseekV3_api.chat import get_response
from deepseekV3_api.characters import teacher, little_horse, yellow_cow, squirrel, narrator

# 定义 normalize_wake_word 函数
def normalize_wake_word(text):
    """去除唤醒词中的所有符号，只保留字母和数字"""
    return re.sub(r'[^\w\s]', '', text).strip()

class VideoPlayer:
    def __init__(self, root, video_path):
        self.root = root
        self.video_path = video_path
        
        # 添加处理语音和等待唤醒词的标志
        self.processing_speech = False
        self.waiting_for_wake_word = True
        self.speech_timeout = 4  # 语音超时时间（秒）
        
        # 初始化pygame混音器用于播放音频
        pygame.mixer.init()
        
        # 创建主框架
        self.main_frame = ttk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建视频显示区域
        self.video_frame = ttk.Frame(self.main_frame)
        self.video_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.video_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 创建控制区域
        self.control_frame = ttk.Frame(self.main_frame)
        self.control_frame.pack(fill=tk.X, pady=10)
        
        # 创建状态显示区域
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(self.status_frame, text="准备就绪")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        self.character_label = ttk.Label(self.status_frame, text="当前角色: 无")
        self.character_label.pack(side=tk.RIGHT, padx=5)
        
        # 创建文本显示区域
        self.text_frame = ttk.Frame(self.main_frame)
        self.text_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.text_display = tk.Text(self.text_frame, height=5, wrap=tk.WORD)
        self.text_display.pack(fill=tk.BOTH, expand=True)
        self.text_display.config(state=tk.DISABLED)
        
        # 初始化视频捕获
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            messagebox.showerror("错误", f"无法打开视频文件: {video_path}")
            root.destroy()
            return
        
        # 获取视频属性
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 调整窗口大小
        root.geometry(f"{self.width}x{self.height + 200}")
        
        # 初始化语音识别
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000  # 调整灵敏度
        self.recognizer.dynamic_energy_threshold = True
        
        # 定义唤醒词映射到角色
        self.raw_wake_words = {
            "机器人机器人": teacher,
            "课本课本": teacher,
            "AIAI": teacher,
            "小爱小爱": teacher,
            "小马小马": little_horse,
            "老牛老牛": yellow_cow,
            "松鼠松鼠": squirrel,
            "旁边旁边": narrator,
            "退出系统": "exit"  # 添加退出系统唤醒词
        }
        
        # 创建规范化的唤醒词映射
        self.wake_words = {}
        for word, character in self.raw_wake_words.items():
            normalized = normalize_wake_word(word)
            self.wake_words[normalized] = character
        
        self.current_character = None
        
        # 开始播放视频
        self.is_playing = True
        self.update_frame()
        
        # 启动语音监听线程
        self.listening = True
        self.listen_thread = threading.Thread(target=self.listen_for_wake_word)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        
        # 绑定关闭事件
        root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def update_frame(self):
        if self.is_playing:
            ret, frame = self.cap.read()
            if ret:
                # 转换颜色空间从BGR到RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 调整画布大小
                self.canvas.config(width=self.width, height=self.height)
                
                # 转换为PhotoImage
                img = Image.fromarray(frame_rgb)
                img_tk = ImageTk.PhotoImage(image=img)
                
                # 更新画布
                self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
                self.canvas.img_tk = img_tk  # 保持引用
                
                # 计算下一帧的延迟时间（毫秒）
                delay = int(1000 / self.fps)
                
                # 安排下一帧更新
                self.root.after(delay, self.update_frame)
            else:
                # 视频结束，重新开始
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.root.after(1, self.update_frame)
    
    def listen_for_wake_word(self):
        """持续监听麦克风输入，检测唤醒词"""
        with sr.Microphone() as source:
            # 调整麦克风环境噪音
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            self.update_status("正在等待唤醒词...")
            
            while self.listening:
                try:
                    # 如果正在处理语音，则跳过
                    if self.processing_speech:
                        time.sleep(0.1)
                        continue
                    
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    self.update_status("正在处理语音...")
                    
                    # 尝试识别语音
                    text = self.recognizer.recognize_google(audio, language="zh-CN")
                    self.update_status(f"识别到: {text}")
                    
                    # 规范化识别文本
                    normalized_text = normalize_wake_word(text)
                    
                    # 检查是否包含唤醒词
                    wake_word_detected = False
                    for wake_word, character in self.wake_words.items():
                        if wake_word in normalized_text:
                            wake_word_detected = True
                            if character == "exit":  # 处理退出系统命令
                                self.update_status("正在退出系统...")
                                self.append_text("\n系统: 谢谢使用，再见!")
                                self.root.after(2000, self.on_close)
                                return
                            else:
                                self.activate_character(character)
                                # 设置标志，表示正在处理语音
                                self.processing_speech = True
                                # 启动一个线程来处理单次语音输入
                                threading.Thread(target=self.process_single_speech, args=(character,)).start()
                            break
                    
                    # 如果没有检测到唤醒词，且不在等待唤醒词状态，则忽略输入
                    if not wake_word_detected and not self.waiting_for_wake_word:
                        self.update_status("请先说出唤醒词")
                    
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    self.update_status("未能识别语音")
                except Exception as e:
                    self.update_status(f"错误: {str(e)}")
                
                time.sleep(0.1)  # 短暂暂停，减少CPU使用
    
    def process_single_speech(self, character):
        """处理单次语音输入"""
        try:
            # 添加倒计时提醒
            for i in range(3, 0, -1):
                self.update_status(f"请准备说话... {i}秒")
                time.sleep(1)
            
            self.update_status("请开始说话...")
            
            # 等待用户输入
            with sr.Microphone() as source:
                try:
                    # 给用户时间说话，最多10秒，超过4秒无声会自动结束
                    audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=10)
                    self.update_status("正在处理您的问题...")
                    
                    # 识别语音
                    text = self.recognizer.recognize_google(audio, language="zh-CN")
                    self.update_status(f"识别到: {text}")
                    
                    # 处理用户输入
                    self.process_input(text)
                    
                except sr.WaitTimeoutError:
                    self.update_status("未检测到语音输入，请重新唤醒")
                except sr.UnknownValueError:
                    self.update_status("未能识别语音，请重新唤醒")
                except Exception as e:
                    self.update_status(f"处理语音时出错: {str(e)}")
            
            # 处理完成后，重置标志
            self.processing_speech = False
            self.waiting_for_wake_word = True
            self.update_status("处理完成，等待唤醒词...")
            
        except Exception as e:
            self.update_status(f"处理单次语音输入时出错: {str(e)}")
            self.processing_speech = False
            self.waiting_for_wake_word = True
    
    def activate_character(self, character):
        """激活指定角色"""
        self.current_character = character
        self.update_character_label(f"当前角色: {character['name']}")
        self.update_status(f"{character['name']}已激活")
        self.waiting_for_wake_word = False
        
        # 显示角色的问候语
        if "greeting" in character:
            self.append_text(f"{character['name']}的问候:\n{character['greeting']}")
    
    def process_input(self, text):
        """处理用户输入，获取角色响应"""
        if not self.current_character:
            return
        
        self.append_text(f"\n您: {text}")
        self.update_status("正在生成回复...")
        
        # 创建线程处理响应，避免界面卡顿
        threading.Thread(target=self._get_response_thread, args=(text,)).start()
    
    def _get_response_thread(self, text):
        """在单独的线程中获取响应"""
        try:
            response = get_response(self.current_character, text)
            
            # 移除括号中的内容用于显示
            display_response = re.sub(r'\([^)]*\)', '', response)
            
            self.append_text(f"\n{self.current_character['name']}: {display_response}")
            
            # 查找并播放生成的语音文件
            speech_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speech_files")
            if os.path.exists(speech_dir):
                # 获取最新生成的语音文件
                files = [os.path.join(speech_dir, f) for f in os.listdir(speech_dir) 
                         if f.endswith('.mp3') and f.startswith(f"{self.current_character['name']}_")]
                if files:
                    latest_file = max(files, key=os.path.getctime)
                    self.update_status(f"正在播放语音...")
                    
                    # 使用pygame播放音频
                    try:
                        pygame.mixer.music.load(latest_file)
                        pygame.mixer.music.play()
                        # 等待音频播放完成
                        while pygame.mixer.music.get_busy():
                            time.sleep(0.1)
                    except Exception as e:
                        self.update_status(f"播放语音时出错: {str(e)}")
            
            self.update_status("准备就绪")
        except Exception as e:
            self.update_status(f"生成回复时出错: {str(e)}")
    
    def update_status(self, text):
        """更新状态标签"""
        def _update():
            self.status_label.config(text=text)
        self.root.after(0, _update)
    
    def update_character_label(self, text):
        """更新当前角色标签"""
        def _update():
            self.character_label.config(text=text)
        self.root.after(0, _update)
    
    def append_text(self, text):
        """向文本区域添加文本"""
        def _append():
            self.text_display.config(state=tk.NORMAL)
            self.text_display.insert(tk.END, text + "\n")
            self.text_display.see(tk.END)
            self.text_display.config(state=tk.DISABLED)
        self.root.after(0, _append)
    
    def on_close(self):
        """关闭窗口时的清理操作"""
        self.is_playing = False
        self.listening = False
        if self.cap.isOpened():
            self.cap.release()
        
        # 清理pygame
        try:
            pygame.mixer.quit()
            pygame.quit()
        except:
            pass
            
        self.root.destroy()

def main():
    # 视频文件路径 - 更新为正确位置
    video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_files", "原始小马（无声）.mp4")
    if not os.path.exists(video_path):
        print(f"错误: 视频文件不存在: {video_path}")
        return
    
    # 创建主窗口
    root = tk.Tk()
    root.title("小马过河交互舞台")
    
    # 创建视频播放器
    player = VideoPlayer(root, video_path)
    
    # 启动主循环
    root.mainloop()

if __name__ == "__main__":
    main()