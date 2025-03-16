import threading
import time
import queue
import os
import dotenv

# 在程序开始时加载环境变量
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(dotenv_path):
    dotenv.load_dotenv(dotenv_path)
    print("环境变量文件已加载")
    
    # 直接从文件读取API密钥
    try:
        with open(dotenv_path, 'r') as f:
            env_content = f.read()
            for line in env_content.split('\n'):
                if line.startswith('OPENAI_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    # 同时设置两个环境变量
                    os.environ["DEEPSEEK_API_KEY"] = api_key
                    os.environ["OPENAI_API_KEY"] = api_key
                    print("已从.env文件直接读取API密钥")
                    print(f"成功获取API密钥: {api_key[:5]}...{api_key[-5:]}")
                    break
    except Exception as e:
        print(f"读取.env文件时出错: {e}")
else:
    print("警告: 环境变量文件不存在")

# 修改导入语句，使用简化版STT
from STT.simple_stt import StreamSTT
from deepseekV3_api.chat import get_response
from deepseekV3_api.characters import little_horse
from deepseekV3_api.generate_speech import generate_speech_chunk

# 创建队列用于组件间通信
stt_queue = queue.Queue()
llm_queue = queue.Queue()
# 添加一个新的控制队列，用于控制STT线程的状态
control_queue = queue.Queue()

# 添加唤醒词和系统状态
WAKE_WORD = "小马小马"
SILENCE_TIMEOUT = 2.0  # 停顿超时时间(秒)

# 确保character对象包含system_prompt
if not hasattr(little_horse, 'system_prompt') or not little_horse.get('system_prompt'):
    little_horse['system_prompt'] = "你是一个友好的AI助手，名叫小马。请用简短、友好的语言回答问题。"

def stt_worker():
    """STT工作线程"""
    stt = StreamSTT()
    stt.start_listening()
    print("开始监听，请说话...")
    
    last_text = ""
    is_activated = False  # 是否已被唤醒
    is_paused = False     # 是否暂停监听
    last_speech_time = time.time()  # 上次语音时间
    
    try:
        while True:
            # 检查控制队列，是否需要暂停或恢复监听
            try:
                control_msg = control_queue.get_nowait()
                if control_msg == "pause":
                    is_paused = True
                    is_activated = False  # 重置激活状态
                    print("麦克风监听已暂停，等待语音播放完成...")
                elif control_msg == "resume":
                    is_paused = False
                    print("麦克风监听已恢复，请说出唤醒词...")
                control_queue.task_done()
            except queue.Empty:
                pass
            
            # 如果暂停状态，跳过语音处理
            if is_paused:
                time.sleep(0.1)
                continue
                
            current_text = stt.get_text()
            
            # 只处理新增的文本
            if current_text and current_text != last_text:
                # 获取新增部分
                new_text = current_text[len(last_text):]
                if new_text.strip():
                    print(f"识别到新内容: {new_text}")
                    
                    # 更新上次语音时间
                    last_speech_time = time.time()
                    
                    # 检查是否包含唤醒词（不区分大小写）
                    if WAKE_WORD.lower() in current_text.lower():
                        is_activated = True
                        print("系统已唤醒！")
                        # 移除唤醒词，只保留后面的内容
                        wake_word_pos = current_text.lower().find(WAKE_WORD.lower()) + len(WAKE_WORD)
                        clean_text = current_text[wake_word_pos:].strip()
                        print(f"处理后的文本: '{clean_text}'")
                        if clean_text:
                            stt_queue.put(clean_text)
                    # 如果已唤醒，则处理文本
                    elif is_activated:
                        stt_queue.put(new_text)
                
                last_text = current_text
            
            # 检查是否超时
            if is_activated and time.time() - last_speech_time > SILENCE_TIMEOUT:
                print(f"检测到{SILENCE_TIMEOUT}秒静音，系统已休眠，需要重新唤醒")
                is_activated = False
            
            time.sleep(0.1)
    except Exception as e:
        print(f"STT错误: {str(e)}")
    finally:
        stt.stop_listening()

# 修改llm_worker函数，增加本地模拟响应
def llm_worker():
    """LLM工作线程"""
    character = little_horse
    print(f"当前角色: {character['name']}")
    
    # 确保character对象包含必要的字段
    print(f"角色配置: {character}")
    
    # 累积的用户输入
    accumulated_input = ""
    # 是否正在处理请求
    is_processing = False
    
    # 本地响应模板，用于API调用失败时
    local_responses = {
        "你好": "你好啊！我是小马，很高兴认识你！",
        "你是谁": "我是小马，一个友好的AI助手。我可以陪你聊天，回答问题，或者讲故事给你听！",
        "讲个故事": "从前有一匹小马，它每天都要过河去上学。有一天河水涨了，小马不知道河水有多深。它先问了牛伯伯，又问了松鼠，得到了不同的建议。最后小马决定自己试一试，发现河水并不深，成功过了河。这个故事告诉我们，实践是检验真理的唯一标准。",
        "今天天气怎么样": "我没法知道今天的实际天气，因为我是一个AI助手。不过无论天气如何，希望你的心情都是晴朗的！",
        "家在哪里": "我的家在美丽的草原上，那里有清澈的小河和广阔的草地。我和妈妈住在一起，每天都很开心！",
        "想买什么": "我想买一些胡萝卜和苹果，这是我最喜欢的食物。你喜欢吃什么呢？",
        "抱歉": "没关系的，不用道歉。我们可以继续聊天！",
    }
    
    try:
        while True:
            # 检查是否有新的STT输入
            try:
                while not stt_queue.empty():
                    new_text = stt_queue.get_nowait()
                    accumulated_input += new_text
                    print(f"累积输入: '{accumulated_input}'")
            except queue.Empty:
                pass
            
            # 如果有累积的输入且当前没有处理请求，开始处理
            if accumulated_input and not is_processing:
                is_processing = True
                print(f"处理输入: '{accumulated_input}'")
                
                try:
                    # 尝试使用DeepSeek API获取响应
                    api_success = False
                    # 修改这里：使用get_response替代get_streaming_response
                    response = get_response(character, accumulated_input)
                    
                    if response:
                        api_success = True
                        # 将完整响应分成小块发送，模拟流式响应
                        for i in range(0, len(response), 10):
                            chunk = response[i:i+10]
                            print(f"响应片段: {chunk}")
                            llm_queue.put(chunk)
                            time.sleep(0.1)  # 添加延迟，模拟流式响应
                    
                    # 如果API调用失败，使用本地响应
                    if not api_success:
                        print("使用本地响应模式")
                        # 查找匹配的本地响应
                        response_text = None
                        for key, value in local_responses.items():
                            if key in accumulated_input.lower():
                                response_text = value
                                break
                        
                        # 如果没有匹配的响应，使用默认回复
                        if not response_text:
                            response_text = "你好！我是小马。我住在草原上，喜欢吃胡萝卜和苹果。很高兴和你聊天！"
                        
                        print(f"本地响应: {response_text}")
                        # 将响应分成小块发送，模拟流式响应
                        for i in range(0, len(response_text), 10):
                            chunk = response_text[i:i+10]
                            llm_queue.put(chunk)
                            time.sleep(0.1)  # 添加延迟，模拟流式响应
                
                except Exception as e:
                    print(f"LLM处理错误: {str(e)}")
                    # 使用默认响应
                    default_response = "抱歉，我遇到了一些问题。我是小马，很高兴认识你！"
                    for i in range(0, len(default_response), 10):
                        chunk = default_response[i:i+10]
                        llm_queue.put(chunk)
                        time.sleep(0.1)
                
                # 重置状态
                accumulated_input = ""
                is_processing = False
                # 发送一个特殊标记表示响应结束
                llm_queue.put("__END__")
            
            time.sleep(0.1)
    except Exception as e:
        print(f"LLM错误: {str(e)}")

# 修改tts_worker函数，增加本地TTS备选方案
def tts_worker():
    """TTS工作线程"""
    try:
        while True:
            # 收集完整的响应
            response_text = ""
            try:
                while not llm_queue.empty():
                    chunk = llm_queue.get_nowait()
                    response_text += chunk
                    llm_queue.task_done()
                    
                    # 打印响应片段
                    print(f"响应片段: {chunk}")
            except queue.Empty:
                pass
            
            # 如果有响应文本，生成并播放语音
            if response_text:
                # 在播放语音前暂停麦克风监听
                control_queue.put("pause")
                
                # 生成语音
                speech_file = generate_speech_chunk(response_text)
                
                # 播放完成后恢复麦克风监听
                control_queue.put("resume")
                
            time.sleep(0.1)
    except Exception as e:
        print(f"TTS错误: {str(e)}")

# 修改main函数，添加新的TTS线程
def main():
    """主函数"""
    print("启动流式语音对话系统...")
    print(f"唤醒词: '{WAKE_WORD}'，停顿超时: {SILENCE_TIMEOUT}秒")
    
    # 创建并启动STT线程
    stt_thread = threading.Thread(target=stt_worker)
    stt_thread.daemon = True
    stt_thread.start()
    
    # 创建并启动LLM线程
    llm_thread = threading.Thread(target=llm_worker)
    llm_thread.daemon = True
    llm_thread.start()
    
    # 创建并启动TTS线程
    tts_thread = threading.Thread(target=tts_worker)
    tts_thread.daemon = True
    tts_thread.start()
    
    # 等待线程结束
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n程序已终止")

if __name__ == "__main__":
    main()