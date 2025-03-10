#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
STT_TTS 项目主入口
集成了语音识别(STT)和语音合成(TTS)功能
"""

import os
import sys
import argparse

# 添加子项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'STT'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'deepseekV3_api'))

def main():
    parser = argparse.ArgumentParser(description='STT_TTS 语音识别与合成工具')
    parser.add_argument('--mode', choices=['stt', 'tts', 'chat'], default='chat',
                        help='运行模式: stt(语音识别), tts(语音合成), chat(对话模式)')
    args = parser.parse_args()
    
    if args.mode == 'stt':
        # 导入并运行 STT 模块
        from STT.SenseVoice.api import app as stt_app
        import uvicorn
        uvicorn.run(stt_app, host="0.0.0.0", port=8000)
    
    elif args.mode == 'tts':
        # 导入并运行 TTS 模块
        from deepseekV3_api.create_voice import main as create_voice_main
        create_voice_main()
    
    elif args.mode == 'chat':
        # 导入并运行聊天模块
        from deepseekV3_api.chat import main as chat_main
        chat_main()

if __name__ == "__main__":
    main()