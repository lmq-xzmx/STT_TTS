from openai import OpenAI
import os
import sys
import re
from pathlib import Path
import time
from dotenv import load_dotenv
from characters import teacher, little_horse, yellow_cow, squirrel, narrator

# 导入文件管理模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.file_manager import cleanup_speech_files, get_directory_size

# 指定.env文件的绝对路径
dotenv_path = '/Users/xzmx/Downloads/my-project/STT_TTS/.env'
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print("环境变量文件已加载")
else:
    print("警告: 环境变量文件不存在")

# 直接从.env文件读取API密钥
api_key = None
try:
    with open(dotenv_path, 'r') as f:
        env_content = f.read()
        for line in env_content.split('\n'):
            if line.startswith('OPENAI_API_KEY='):
                # 移除可能的引号和空格
                api_key = line.split('=', 1)[1].strip().strip('"\'')
                print("已从.env文件直接读取API密钥")
                break
except Exception as e:
    print(f"读取.env文件时出错: {e}")

if not api_key:
    print("错误: 无法获取API密钥，请检查.env文件")
    sys.exit(1)
else:
    # 确保API密钥没有前后空格或引号
    api_key = api_key.strip().strip('"\'')
    print(f"成功获取API密钥: {api_key[:5]}...{api_key[-5:]}")
    # 验证API密钥格式
    if not api_key.startswith("sk-"):
        print("警告: API密钥格式可能不正确，应以'sk-'开头")

# 语音文件存储目录
speech_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "speech_files"
if not speech_dir.exists():
    speech_dir.mkdir(parents=True)
    print(f"已创建语音文件存储目录: {speech_dir}")

# 用户音色信息存储目录
user_voices_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "user_voices"
if not user_voices_dir.exists():
    user_voices_dir.mkdir(parents=True)
    print(f"已创建用户音色信息存储目录: {user_voices_dir}")

# 初始化OpenAI客户端
client = OpenAI(
    api_key=api_key,  # 使用处理过的API密钥
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
)

# 从环境变量获取模型配置
TEXT_MODEL = os.getenv("TEXT_MODEL", "deepseek-ai/DeepSeek-V3")
VOICE_MODEL = os.getenv("VOICE_MODEL", "FunAudioLLM/CosyVoice2-0.5B")
DEFAULT_VOICE_ID = os.getenv("VOICE_ID", "speech:xiaoma:4on1q9y2b5:smwvoogtaqejdkgmfxpq")

# 添加一个测试函数来验证API连接
def test_api_connection():
    """测试API连接是否正常"""
    try:
        print("正在测试API连接...")
        # 尝试一个简单的API调用
        response = client.models.list()
        print("API连接测试成功！")
        return True
    except Exception as e:
        print(f"API连接测试失败: {e}")
        return False

def get_response(character, user_input):
    """获取指定角色的响应并生成语音"""
    messages = character["messages"].copy()
    messages.append({"role": "user", "content": user_input})
    
    # 使用角色特定的温度参数，如果没有则使用默认值
    temperature = character.get("temperature", 0.7)
    
    response = client.chat.completions.create(
        model=TEXT_MODEL,  # 使用环境变量中的文本模型
        messages=messages,
        temperature=temperature,
        max_tokens=1024,
        stream=True
    )
    
    # 存储完整响应
    full_response = ""
    
    # 逐步接收并处理响应
    print(f"\n{character['name']}的回答:")
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="", flush=True)
            full_response += content
    
    # 将对话历史添加到角色的消息列表中
    character["messages"].append({"role": "user", "content": user_input})
    character["messages"].append({"role": "assistant", "content": full_response})
    
    # 使用预置音色ID
    voice_id = character.get("voice_id", DEFAULT_VOICE_ID)
    
    # 清理旧的语音文件
    cleanup_speech_files(speech_dir)
    
    # 生成唯一的文件名
    timestamp = int(time.time())
    speech_file_path = speech_dir / f"{character['name']}_{timestamp}.mp3"
    
    try:
        print(f"\n正在生成{character['name']}的语音...")
        with client.audio.speech.with_streaming_response.create(
            model=VOICE_MODEL,  # 使用环境变量中的语音模型
            voice=voice_id,
            input=full_response,
            response_format="mp3"
        ) as response:
            response.stream_to_file(speech_file_path)
        print(f"语音生成成功！文件保存在: {speech_file_path}")
    except Exception as e:
        print(f"生成语音时出错: {e}")
    
    return full_response

def normalize_wake_word(text):
    """去除唤醒词中的所有符号，只保留字母和数字"""
    return re.sub(r'[^\w\s]', '', text).strip()

def main():
    print("欢迎来到小马过河互动故事系统!")
    
    # 测试API连接
    if not test_api_connection():
        print("无法连接到API服务，请检查API密钥和网络连接")
        print("您可以尝试以下解决方案:")
        print("1. 检查.env文件中的API密钥是否正确")
        print("2. 确认网络连接是否正常")
        print("3. 确认API服务是否可用")
        return
    
    print("可用角色及唤醒词:")
    print("1.课本讲解机器人 - 唤醒词: 机器人机器人、课本课本、AIAI、小爱小爱")
    print("2.小马 - 唤醒词: 小马小马")
    print("3.大黄牛 - 唤醒词: 老牛老牛")
    print("4.小松鼠 - 唤醒词: 松鼠松鼠")
    print("5.旁白者 - 唤醒词: 旁边旁边")
    print("输入 'exit' 退出系统")
    
    # 设置角色的语音ID - 使用预置音色
    voice_id = "speech:xiaoma:4on1q9y2b5:smwvoogtaqejdkgmfxpq"
    little_horse["voice_id"] = voice_id
    teacher["voice_id"] = voice_id
    yellow_cow["voice_id"] = voice_id
    squirrel["voice_id"] = voice_id
    narrator["voice_id"] = voice_id
    
    # 定义唤醒词映射到角色（去掉逗号）
    raw_wake_words = {
        "机器人机器人": teacher,
        "课本课本": teacher,
        "AIAI": teacher,
        "小爱小爱": teacher,
        "小马小马": little_horse,
        "老牛老牛": yellow_cow,
        "松鼠松鼠": squirrel,
        "旁边旁边": narrator
    }
    
    # 创建规范化的唤醒词映射
    wake_words = {}
    for word, character in raw_wake_words.items():
        normalized = normalize_wake_word(word)
        wake_words[normalized] = character
    
    current_character = None
    
    while True:
        try:
            if current_character is None:
                user_input = input("\n请说出唤醒词或输入 'exit' 退出: ")
            else:
                user_input = input(f"\n请输入您想对{current_character['name']}说的话 (或使用其他唤醒词切换角色，输入'exit'退出): ")
            
            if user_input.lower() == 'exit' or user_input == '退出系统':
                print("谢谢使用，再见!")
                break
            
            # 规范化用户输入，去除所有符号
            normalized_input = normalize_wake_word(user_input)
            
            # 检查是否是唤醒词
            if normalized_input in wake_words:
                current_character = wake_words[normalized_input]
                print(f"\n{current_character['name']}选择成功，可以开始对话。")
                
                # 显示角色的问候语
                if "greeting" in current_character:
                    print(f"\n{current_character['name']}的问候:")
                    print(current_character["greeting"])
                continue
            
            # 如果没有选择角色，提示用户
            if current_character is None:
                print("请先使用唤醒词选择一个角色")
                continue
            
            # 处理用户输入
            get_response(current_character, user_input)
            
        except Exception as e:
            print(f"发生错误: {e}")

if __name__ == "__main__":
    main()