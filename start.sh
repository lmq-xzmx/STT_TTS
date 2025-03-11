#!/bin/bash

# 设置基本路径变量
SCRIPT_DIR="/Users/xzmx/Downloads/my-project/STT_TTS"
VENV_PATH="$SCRIPT_DIR/venv_py310"

echo "===== Python 3.10 虚拟环境配置脚本 ====="

# 查找 Python 3.10 安装
echo "正在查找 Python 3.10..."
PYTHON310="/usr/local/bin/python3.10"

# 检查 Python 3.10 是否存在
if [ ! -f "$PYTHON310" ]; then
  echo "错误: 找不到 Python 3.10"
  echo "请使用以下命令安装: brew install python@3.10"
  exit 1
fi

echo "找到 Python 3.10: $PYTHON310"
echo "版本: $($PYTHON310 --version)"

# 删除旧的虚拟环境(如果存在)
if [ -d "$VENV_PATH" ]; then
  echo "删除旧的虚拟环境..."
  /bin/rm -rf "$VENV_PATH"
fi

# 创建新的虚拟环境 - 使用 --clear 确保完全重建
echo "使用 Python 3.10 创建新的虚拟环境..."
$PYTHON310 -m venv "$VENV_PATH" --clear

# 检查虚拟环境是否创建成功
if [ ! -d "$VENV_PATH" ]; then
  echo "错误: 虚拟环境创建失败"
  exit 1
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source "$VENV_PATH/bin/activate"

# 验证 Python 版本
PY_VERSION=$(python --version)
echo "当前 Python 版本: $PY_VERSION"

# 检查是否是 Python 3.10
if [[ "$PY_VERSION" != *"3.10"* ]]; then
  echo "警告: 虚拟环境不是使用 Python 3.10"
  echo "当前版本: $PY_VERSION"
  echo "尝试修复问题..."
  
  # 更新 pyvenv.cfg 文件
  echo "home = $(/usr/bin/dirname $(/usr/bin/dirname $PYTHON310))" > "$VENV_PATH/pyvenv.cfg"
  echo "include-system-site-packages = false" >> "$VENV_PATH/pyvenv.cfg"
  echo "version = 3.10.16" >> "$VENV_PATH/pyvenv.cfg"
  echo "executable = $PYTHON310" >> "$VENV_PATH/pyvenv.cfg"
  echo "command = $PYTHON310 -m venv $VENV_PATH" >> "$VENV_PATH/pyvenv.cfg"
  
  # 重新安装 pip
  echo "重新安装 pip..."
  curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
  $PYTHON310 /tmp/get-pip.py --force-reinstall
  
  echo "请重新运行此脚本"
  exit 1
fi

echo ""
echo "===== 虚拟环境已激活 ====="
echo "虚拟环境路径: $VENV_PATH"
echo "Python 版本: $PY_VERSION"
echo ""
echo "您现在可以运行项目了！"
echo "退出虚拟环境请输入: deactivate"

# 切换到项目目录
cd "$SCRIPT_DIR"
echo "已切换到项目目录: $SCRIPT_DIR"

# 提示安装依赖
echo "如果需要安装依赖，请运行:"
echo "pip install torch torchaudio openai python-dotenv pyaudio pygame funasr kaldi_native_fbank sentencepiece"