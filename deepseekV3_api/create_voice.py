import requests
import os
import json
import shutil
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

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

# 设置用户音色目录
user_voices_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_voices")
if not os.path.exists(user_voices_dir):
    os.makedirs(user_voices_dir)
    print(f"已创建用户音色目录: {user_voices_dir}")

# 请用户选择音频文件
print("请选择参考音频文件:")
print("1. 使用默认音频文件 (deepseekV3_api/vice/xiao.mp3)")
print("2. 指定其他音频文件路径")
choice = input("请输入选项 (1/2): ")

if choice == "2":
    audio_file_path = input("请输入音频文件的完整路径: ")
    if not os.path.exists(audio_file_path):
        print(f"错误: 文件 {audio_file_path} 不存在")
        exit(1)
else:
    # 使用默认音频文件路径
    audio_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vice", "xiao.mp3")
    if not os.path.exists(audio_file_path):
        print(f"错误: 默认文件 {audio_file_path} 不存在")
        exit(1)

# 获取文件名
audio_file_name = os.path.basename(audio_file_path)

# 复制文件到用户音色目录
target_file_path = os.path.join(user_voices_dir, audio_file_name)
if audio_file_path != target_file_path:  # 避免复制到自身
    try:
        shutil.copy2(audio_file_path, target_file_path)
        print(f"已将音频文件复制到: {target_file_path}")
    except Exception as e:
        print(f"复制文件时出错: {e}")

# 请输入参考音频的文字内容
reference_text = input("请输入参考音频的文字内容: ")
if not reference_text:
    print("错误: 参考音频的文字内容不能为空")
    exit(1)

# 自定义音色名称
user_input = input("请输入自定义音色名称 (直接按回车使用默认名称): ")

# 如果用户没有输入，使用默认名称格式：voice_序号_时间戳
if not user_input:
    # 获取当前时间戳
    import time
    timestamp = int(time.time())
    
    # 读取README.md文件，计算当前音色序号
    readme_path = os.path.join(user_voices_dir, "README.md")
    voice_count = 1  # 默认序号从1开始
    
    if os.path.exists(readme_path):
        try:
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
                table_lines = [line for line in content.split('\n') if line.startswith('|') and '|' in line[1:]]
                if len(table_lines) > 2:
                    voice_count = len(table_lines) - 2 + 1
        except Exception as e:
            print(f"读取README.md时出错: {e}")
    
    # 生成符合规则的默认名称
    custom_name = f"voice_{voice_count}_{timestamp}"
    print(f"使用默认名称: {custom_name}")
else:
    # 处理用户输入的名称，确保符合API要求
    import re
    # 只保留字母、数字、下划线和连字符
    custom_name = re.sub(r'[^a-zA-Z0-9_-]', '_', user_input)
    # 确保长度不超过64个字符
    custom_name = custom_name[:64]
    if custom_name != user_input:
        print(f"已将音色名称规范化为: {custom_name}")

# 打开音频文件
files = {
    "file": open(target_file_path, "rb")  # 使用复制后的音频文件
}

# 设置请求数据
data = {
    "model": "FunAudioLLM/CosyVoice2-0.5B",  # 模型名称
    "customName": custom_name,  # 自定义音色名称
    "text": reference_text  # 参考音频的文字内容
}

# 设置请求参数
url = "https://api.siliconflow.cn/v1/uploads/audio/voice"
headers = {
    "Authorization": f"Bearer {api_key}"  # 使用从.env文件读取的API密钥
}

# 发送请求
try:
    print("正在上传音频文件并创建自定义音色...")
    response = requests.post(url, headers=headers, files=files, data=data)
    
    # 打印响应状态码和内容
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        print("自定义音色创建成功!")
        response_data = response.json()
        print("响应内容:")
        print(response_data)
        
        # 获取完整的音色ID (uri)
        voice_id = response_data.get("uri", "")
        if not voice_id and "id" in response_data:
            voice_id = response_data.get("id", "")
        
        # 更新README.md文件
        readme_path = os.path.join(user_voices_dir, "README.md")
        
        # 获取相对路径
        relative_path = os.path.relpath(target_file_path, os.path.dirname(readme_path))
        
        # 获取当前日期
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        if os.path.exists(readme_path):
            # 读取现有内容
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 构建新的音色信息行
            new_voice_info = f"| {custom_name} | {voice_id} | {current_date} | 由create_voice.py创建，来自文件 {relative_path} |"
            
            # 在表格中添加新行
            if "| 音色名称 | 音色ID | 创建日期 | 描述 |" in content:
                table_line = content.find("| 音色名称 | 音色ID | 创建日期 | 描述 |")
                next_line = content.find("\n", table_line) + 1
                separator_line = content.find("\n", next_line) + 1
                
                # 在表格分隔符后添加新行
                updated_content = content[:separator_line] + new_voice_info + "\n" + content[separator_line:]
                
                # 写回文件
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                
                print(f"已更新音色信息到 {readme_path}")
            else:
                print(f"无法在 {readme_path} 中找到音色表格，请手动更新")
        else:
            # 如果README.md不存在，创建一个新的
            readme_content = f"""# 用户音色信息记录

本文件夹用于存放已生成的用户音色信息文件。

## 音色列表

| 音色名称 | 音色ID | 创建日期 | 描述 |
|---------|-------|---------|-----|
| {custom_name} | {voice_id} | {current_date} | 由create_voice.py创建，来自文件 {relative_path} |

## 使用说明

1. 所有音色文件应存放在此文件夹中
2. 音色文件命名格式：`[音色名称]_[创建日期].mp3`
3. 请在上方表格中记录新添加的音色信息

## 注意事项

- 请勿删除此文件夹中的音色文件
- 添加新音色后，请更新此文档
"""
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            print(f"已创建并更新音色信息到 {readme_path}")
    else:
        print("创建自定义音色失败")
        print("错误信息:")
        print(response.text)
except Exception as e:
    print(f"请求过程中发生错误: {e}")
finally:
    # 关闭文件
    files["file"].close()