#!/bin/bash

# 检查虚拟环境路径是否存在
VENV_PATH="/Users/xzmx/Downloads/my-project/STT_TTS/venv/bin/activate"
if [ ! -f "$VENV_PATH" ]; then
    # 尝试查找原始的SenseVoice_env路径
    VENV_PATH="/Users/xzmx/Downloads/my-project/STT_TTS/STT/SenseVoice/SenseVoice_env/bin/activate"
    if [ ! -f "$VENV_PATH" ]; then
        echo "错误：找不到虚拟环境。请检查路径是否正确。"
        exit 1
    fi
fi

# 激活虚拟环境
source "$VENV_PATH"

# 显示成功信息
echo "虚拟环境已激活！"
echo "当前使用的虚拟环境: $VENV_PATH"
echo "如果需要退出，请键入: deactivate"