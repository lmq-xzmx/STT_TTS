#!/bin/bash

# 设置项目路径和虚拟环境路径
PROJECT_DIR="/Users/xzmx/Downloads/my-project/STT_TTS"
VENV_PATH="$PROJECT_DIR/venv_py310"

# 检查虚拟环境是否存在
if [ ! -d "$VENV_PATH" ]; then
  echo "错误: 虚拟环境不存在，请先运行 start.sh 创建"
  exit 1
fi

# 创建一个临时的 zsh 配置文件
TEMP_RC="/tmp/project_env_$$.zsh"
cat > "$TEMP_RC" << EOF
# 临时环境配置
source "$VENV_PATH/bin/activate"
cd "$PROJECT_DIR"
alias python="$VENV_PATH/bin/python"
alias python3="$VENV_PATH/bin/python"
export PATH="$VENV_PATH/bin:\$PATH"

echo "已进入项目环境:"
echo "- 目录: \$(pwd)"
echo "- Python: \$($VENV_PATH/bin/python --version)"
echo "- python/python3 命令已映射到 Python 3.10"
echo ""
echo "退出环境请输入: exit"

# 设置提示符
PROMPT="(STT_TTS) %n@%m %~ %# "
EOF

# 使用临时配置文件启动新的 zsh
echo "正在进入项目环境..."
ZDOTDIR=/tmp exec zsh -i -c "source $TEMP_RC; exec zsh -i"