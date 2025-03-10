import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.file_manager import cleanup_speech_files, get_directory_size

# 加载环境变量
load_dotenv()

# 语音文件存储目录
speech_dir = Path(os.path.dirname(os.path.abspath(__file__))) / "speech_files"
if not speech_dir.exists():
    speech_dir.mkdir(parents=True)
    print(f"已创建语音文件存储目录: {speech_dir}")

def verify_api_key():
    """验证API密钥并确保.env文件中的密钥被正确使用"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    
    # 读取.env文件中的API密钥
    api_key = None
    try:
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('OPENAI_API_KEY='):
                    api_key = line.split('=', 1)[1].strip().strip('"\'')
                    break
        
        if api_key:
            print(f"从.env文件读取到API密钥: {api_key[:5]}...{api_key[-5:]}")
            
            # 检查deepseekV3_api/chat.py文件中是否使用了正确的API密钥
            chat_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deepseekV3_api', 'chat.py')
            
            # 修改chat.py文件，强制使用.env中的API密钥
            with open(chat_py_path, 'r') as f:
                content = f.read()
            
            # 添加直接设置API密钥的代码
            if "api_key=api_key" in content:
                print("chat.py文件已配置为使用变量中的API密钥，正在更新...")
                # 替换初始化客户端的代码
                new_content = content.replace(
                    "client = OpenAI(\n    api_key=api_key",
                    f"client = OpenAI(\n    api_key='{api_key}'"
                )
                
                with open(chat_py_path, 'w') as f:
                    f.write(new_content)
                print("已更新chat.py文件，使用.env中的API密钥")
            else:
                print("chat.py文件可能已经使用了硬编码的API密钥")
            
            return True
        else:
            print("错误: 在.env文件中未找到API密钥")
            return False
    except Exception as e:
        print(f"验证API密钥时出错: {e}")
        return False

def manage_files():
    """管理语音文件大小"""
    print("\n语音文件管理")
    print("-" * 30)
    
    # 获取当前目录大小
    total_size = get_directory_size(speech_dir)
    print(f"当前语音文件夹大小: {total_size/1024/1024:.2f}MB")
    
    choice = input("\n是否要清理旧文件? (y/n): ")
    if choice.lower() == 'y':
        max_size = input("请输入触发清理的大小阈值(MB，默认200): ")
        target_size = input("请输入清理后的目标大小(MB，默认60): ")
        
        try:
            max_size = int(max_size) if max_size.strip() else 200
            target_size = int(target_size) if target_size.strip() else 60
            
            if max_size <= target_size:
                print("错误: 触发清理的大小必须大于清理后的目标大小")
                return
                
            cleanup_speech_files(speech_dir, max_size, target_size)
        except ValueError:
            print("错误: 请输入有效的数字")
    else:
        print("未进行文件清理")

def main():
    print("欢迎使用语音交互系统!")
    
    # 验证API密钥
    verify_api_key()
    
    print("1. 语音识别 (STT)")
    print("2. 小马过河互动故事")
    print("3. 管理语音文件")
    print("4. 退出")
    
    while True:
        try:
            choice = input("\n请选择功能 (1-4): ")
            
            if choice == '1':
                # 调用 STT 模块
                print("\n正在启动语音识别模块...")
                # 这里可以根据您的 STT 模块的入口点进行调整
                os.system("python /Users/xzmx/Downloads/my-project/STT_TTS/STT/SenseVoice/demo1.py")
            elif choice == '2':
                # 调用 DeepSeek V3 API 模块
                print("\n正在启动小马过河互动故事系统...")
                os.system("python /Users/xzmx/Downloads/my-project/STT_TTS/deepseekV3_api/chat.py")
            elif choice == '3':
                # 管理语音文件
                manage_files()
            elif choice == '4':
                print("谢谢使用，再见!")
                break
            else:
                print("无效的选择，请重新输入")
        except Exception as e:
            print(f"发生错误: {e}")

if __name__ == "__main__":
    main()