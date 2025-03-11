#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# 流式语音交互演示

import os
import time
import threading
from pathlib import Path
import sys

# 添加路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入流式STT
from STT.stream_stt import StreamingSTT

# 导入流式TTS
from deepseekV3_api.generate_speech import stream_and_play_speech

# 导入聊天功能
from deepseekV3_api.chat import get_streaming_response

# 定义角色
character = {
    "name": "小马助手",
    "description": "一个友好、知识渊博的AI助手",
    "messages": [
        {"role": "system", "content": "你是小马助手，一个友好、知识渊博的AI助手。你的回答应该简洁、有帮助且友好。"},
    ]
}

def main():
    print("初始化流式语音交互系统...")
    
    # 初始化流式STT
    stt = StreamingSTT()
    
    print("\n===== 流式语音交互演示 =====")
    print("1. 按Enter开始对话")
    print("2. 说话后停顿会自动识别")
    print("3. 输入'退出'或'exit'结束程序")
    
    while True:
        print("\n准备好了吗？按Enter开始对话...")
        user_input = input()
        
        if user_input.lower() in ['退出', 'exit', 'quit']:
            break
        
        # 开始监听
        print("正在聆听，请说话...")
        stt.start_listening()
        
        # 等待用户说话并识别
        try:
            # 等待识别结果
            timeout = 15  # 最长等待15秒
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # 检查是否有新的识别结果
                result = stt.get_result(timeout=0.5)
                if result:
                    # 有新的识别结果
                    user_text = result
                    break
                
                # 如果超过5秒没有检测到语音，提示用户
                if time.time() - stt.last_speech_time > 5 and not stt.is_speaking:
                    print("没有检测到语音，请说话或按Enter结束...")
                    if input() != "":
                        break
            
            # 获取最终识别结果
            user_text = stt.get_current_text()
            
            # 停止监听
            stt.stop_listening()
            
            if not user_text:
                print("未能识别到语音，请重试")
                continue
            
            print(f"\n用户: {user_text}")
            
            if user_text.lower() in ['退出', 'exit', 'quit']:
                break
            
            # 获取AI响应
            print("\nAI思考中...")
            
            # 使用流式响应
            full_response = ""
            for response_chunk in get_streaming_response(character, user_text):
                full_response += response_chunk
                print(response_chunk, end="", flush=True)
            
            print("\n\n正在生成语音回复...")
            
            # 使用流式TTS生成并播放语音
            speech_file = stream_and_play_speech(full_response)
            
            # 更新对话历史
            character["messages"].append({"role": "user", "content": user_text})
            character["messages"].append({"role": "assistant", "content": full_response})


            # 限制对话历史长度
            if len(character["messages"]) > 10:
                # 保留system消息和最近的对话
                character["messages"] = [character["messages"][0]] + character["messages"][-9:]
            
        except KeyboardInterrupt:
            # 用户中断
            stt.stop_listening()
            print("\n用户中断")
        
        except Exception as e:
            stt.stop_listening()
            print(f"\n发生错误: {e}")
    
    print("感谢使用流式语音交互系统，再见！")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已被用户中断")
    except Exception as e:
        print(f"\n程序运行出错: {e}")
    finally:
        print("程序已退出")