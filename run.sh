#!/usr/bin/env bash
set -euo pipefail

# ViMax 运行脚本
# 用法: ./run.sh [命令] [选项]

SOURCE="${BASH_SOURCE[0]}"
while [[ -L "$SOURCE" ]]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DIR/$SOURCE"
done
ROOT="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示帮助信息
show_help() {
  cat <<EOF
${BLUE}ViMax - Agentic Video Generation${NC}

${GREEN}用法:${NC}
  ./run.sh [命令] [选项]

${GREEN}命令:${NC}
  ${YELLOW}install${NC}                安装所有依赖 (Python + TUI)
  ${YELLOW}tui${NC}                    启动交互式 TUI 界面
    ${YELLOW}new${NC}                   创建新会话
    ${YELLOW}resume${NC}                恢复当前活动会话
    ${YELLOW}resume <session_id>${NC}   恢复指定会话
    
  ${YELLOW}idea2video${NC}             运行 Idea-to-Video 流水线
  ${YELLOW}script2video${NC}           运行 Script-to-Video 流水线
  ${YELLOW}novel2video${NC}            运行 Novel-to-Video 流水线 (完整版)
  ${YELLOW}novel2video-simple${NC}     运行 Novel-to-Video 流水线 (简化版-无向量化)
  
  ${YELLOW}check${NC}                  检查依赖环境
  ${YELLOW}help${NC}                   显示此帮助信息

${GREEN}示例:${NC}
  ./run.sh install            # 首次安装所有依赖
  ./run.sh tui                # 启动 TUI 界面
  ./run.sh tui new            # 创建新会话
  ./run.sh idea2video         # 运行 Idea-to-Video 流水线
  ./run.sh script2video       # 运行 Script-to-Video 流水线
  ./run.sh novel2video-simple # 运行简化版小说转短剧 (推荐)
  ./run.sh novel2video        # 运行完整版小说转短剧
  ./run.sh check              # 检查依赖

${GREEN}环境要求:${NC}
  - Python >= 3.12 (推荐 3.12)
  - uv (Python 包管理器)
  - Node.js + npm (TUI 模式需要)
  - API 密钥 (LLM, 图像生成, 视频生成)

${GREEN}配置:${NC}
  请在以下文件中配置 API 密钥和模型信息:
  - configs/agent.local.yaml      (TUI 模式)
  - configs/idea2video.yaml       (Idea-to-Video 模式)
  - configs/script2video.yaml     (Script-to-Video 模式)

  或使用环境变量:
  - VIMAX_LLM_API_KEY, VIMAX_LLM_MODEL, VIMAX_LLM_BASE_URL
  - VIMAX_IMAGE_API_KEY, VIMAX_IMAGE_MODEL, VIMAX_IMAGE_BASE_URL
  - VIMAX_VIDEO_API_KEY, VIMAX_VIDEO_MODEL, VIMAX_VIDEO_BASE_URL
EOF
}

# 安装依赖
install_deps() {
  echo -e "${BLUE}安装所有依赖...${NC}"
  
  # 安装 Python 依赖
  echo -e "\n${YELLOW}[1/2] 安装 Python 依赖 (uv sync)...${NC}"
  cd "$ROOT"
  UV_PYTHON=python3.12 uv sync
  echo -e "${GREEN}✓${NC} Python 依赖安装完成"
  
  # 安装 TUI 依赖
  if command -v npm &> /dev/null; then
    echo -e "\n${YELLOW}[2/2] 安装 TUI 依赖 (npm install)...${NC}"
    cd "$ROOT/ui"
    npm install
    echo -e "${GREEN}✓${NC} TUI 依赖安装完成"
  else
    echo -e "${YELLOW}!${NC} npm 未安装，跳过 TUI 依赖安装"
  fi
  
  echo -e "\n${GREEN}所有依赖安装完成！${NC}"
}

# 检查依赖
check_dependencies() {
  echo -e "${BLUE}检查依赖环境...${NC}"
  
  # 检查 Python
  if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓${NC} Python3: $(python3 --version)"
  else
    echo -e "${RED}✗${NC} Python3 未安装"
    return 1
  fi
  
  # 检查 uv
  if command -v uv &> /dev/null; then
    echo -e "${GREEN}✓${NC} uv: $(uv --version)"
  else
    echo -e "${RED}✗${NC} uv 未安装 (请安装: https://docs.astral.sh/uv/getting-started/installation/)"
    return 1
  fi
  
  # 检查 Node.js (TUI 需要)
  if command -v node &> /dev/null; then
    echo -e "${GREEN}✓${NC} Node.js: $(node --version)"
  else
    echo -e "${YELLOW}!${NC} Node.js 未安装 (TUI 模式需要)"
  fi
  
  # 检查 npm
  if command -v npm &> /dev/null; then
    echo -e "${GREEN}✓${NC} npm: $(npm --version)"
  else
    echo -e "${YELLOW}!${NC} npm 未安装"
  fi
  
  # 检查 Python 依赖
  echo -e "\n${BLUE}检查 Python 依赖...${NC}"
  if [[ -f "$ROOT/pyproject.toml" ]]; then
    echo -e "${GREEN}✓${NC} pyproject.toml 存在"
  else
    echo -e "${RED}✗${NC} pyproject.toml 不存在"
    return 1
  fi
  
  # 检查 uv 虚拟环境和包
  if [[ -d "$ROOT/.venv" ]]; then
    echo -e "${GREEN}✓${NC} Python 虚拟环境存在"
    # 检查关键包是否安装
    if "$ROOT/.venv/bin/python" -c "import langchain_core" &> /dev/null; then
      echo -e "${GREEN}✓${NC} Python 关键包已安装"
    else
      echo -e "${YELLOW}!${NC} Python 包未安装 (运行: ./run.sh install)"
    fi
  else
    echo -e "${YELLOW}!${NC} Python 虚拟环境未创建 (运行: ./run.sh install)"
  fi
  
  # 检查 TUI 依赖
  echo -e "\n${BLUE}检查 TUI 依赖...${NC}"
  if [[ -d "$ROOT/ui/node_modules" ]]; then
    echo -e "${GREEN}✓${NC} TUI node_modules 已安装"
  else
    echo -e "${YELLOW}!${NC} TUI node_modules 未安装 (运行: cd ui && npm install)"
  fi
  
  echo -e "\n${GREEN}依赖检查完成${NC}"
  return 0
}

# 运行 TUI 模式
run_tui() {
  # 检查 TUI 依赖
  if [[ ! -x "$ROOT/ui/node_modules/.bin/tsx" ]]; then
    echo -e "${RED}错误: TUI 依赖缺失。请运行: cd $ROOT/ui && npm install${NC}" >&2
    exit 2
  fi
  
  echo -e "${BLUE}启动 ViMax TUI...${NC}"
  exec "$ROOT/ui/node_modules/.bin/tsx" "$ROOT/ui/src/cli.tsx" "$@"
}

# 运行 Idea-to-Video 模式
run_idea2video() {
  echo -e "${BLUE}启动 Idea-to-Video 流水线...${NC}"
  cd "$ROOT"
  uv run python main_idea2video.py
}

# 运行 Script-to-Video 模式
run_script2video() {
  echo -e "${BLUE}启动 Script-to-Video 流水线...${NC}"
  cd "$ROOT"
  uv run python main_script2video.py
}

# 运行 Novel-to-Video 模式
run_novel2video() {
  echo -e "${BLUE}启动 Novel-to-Video 流水线...${NC}"
  cd "$ROOT"
  uv run python main_novel2video.py
}

# 运行 Novel-to-Video 简化版 (无向量化)
run_novel2video_simple() {
  echo -e "${BLUE}启动 Novel-to-Video 流水线 (简化版 - 无向量化)...${NC}"
  cd "$ROOT"
  uv run python main_novel2video_simple.py
}

# 主函数
main() {
  if [[ $# -lt 1 ]]; then
    show_help
    exit 2
  fi
  
  command="$1"
  shift
  
  case "$command" in
    install)
      install_deps
      ;;
    tui)
      run_tui "$@"
      ;;
    idea2video)
      run_idea2video
      ;;
    script2video)
      run_script2video
      ;;
    novel2video)
      run_novel2video
      ;;
    novel2video-simple)
      run_novel2video_simple
      ;;
    check)
      check_dependencies
      ;;
    help|--help|-h)
      show_help
      ;;
    *)
      echo -e "${RED}错误: 未知命令 '$command'${NC}" >&2
      echo ""
      show_help
      exit 2
      ;;
  esac
}

# 执行主函数
main "$@"