import os
import re

def clean_requirements_file(file_path):
    """Clean up a requirements.txt file by removing pip output text and keeping only package specifications"""
    if not os.path.exists(file_path):
        print(f"错误: 文件 {file_path} 不存在")
        return
    
    # 读取文件内容
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        # 跳过空行、注释和看起来像pip输出的行
        if not line or line.startswith('#'):
            continue
        if line.startswith('Looking in indexes:') or line.startswith('Processing'):
            continue
        if 'wheel-' in line or '(from' in line:
            continue
        
        # 提取包名和版本（如果是有效的需求）
        if re.match(r'^[a-zA-Z0-9_\-\.]+[<>=!~]?.*$', line):
            cleaned_lines.append(line)
    
    # 如果没有找到有效的包，尝试手动添加基本依赖
    if not cleaned_lines:
        cleaned_lines = [
            "openai",
            "python-dotenv",
            "torch",
            "torchaudio",
            "numpy",
            "fastapi",
            "uvicorn"
        ]
        print("未找到有效的包依赖，已添加基本依赖项")
    
    # 将清理后的内容写回文件
    with open(file_path, 'w') as f:
        f.write('\n'.join(cleaned_lines))
    
    print(f"成功清理 {file_path}")
    print(f"包含的依赖项: {', '.join(cleaned_lines)}")

# 清理 requirements.txt 文件
clean_requirements_file('/Users/xzmx/Downloads/my-project/STT_TTS/requirements.txt')

# 另一种方法：直接创建新的 requirements.txt
def create_new_requirements():
    """创建一个新的 requirements.txt 文件，包含项目所需的基本依赖"""
    requirements = [
        "openai",
        "python-dotenv",
        "torch",
        "torchaudio",
        "numpy",
        "fastapi",
        "uvicorn",
        "pydantic"
    ]
    
    with open('/Users/xzmx/Downloads/my-project/STT_TTS/requirements.txt', 'w') as f:
        f.write('\n'.join(requirements))
    
    print("已创建新的 requirements.txt 文件")
    print(f"包含的依赖项: {', '.join(requirements)}")

# 如果清理失败，可以取消下面这行的注释来创建新的 requirements.txt
# create_new_requirements()