# Stride — 80/20 极化训练法跑步计划

**Stride** 是一套面向严肃跑者的训练管理系统。基于马特·菲茨杰拉德（Matt Fitzgerald）的「80/20 极化训练法」，自动生成科学的分期训练计划，通过连接 COROS 手表实时监测恢复状态（HRV、静息心率、睡眠质量），动态调整每日训练强度。

内置多模型 AI 教练、MediaPipe 视频跑姿分析、赛事配速预测、多平台运动数据导入（Garmin/Apple/华为/小米/Keep/悦跑圈），覆盖从训练规划到执行复盘的全流程。

## 功能

- **训练计划** — 80/20 极化训练自动生成，支持减量周、周跑量递增、自定义强度配比
- **仪表盘** — 恢复状态 (HRV)、VO₂max 趋势、训练负荷 (ATI/CTI)、睡眠分析
- **COROS 同步** — 支持账号密码和 MCP CLI 两种方式同步手表数据。*使用了非官方接口，账号被锁概率极小，但仍需了解相关风险*
- **AI 教练** — 多模型支持 (DeepSeek / Anthropic / OpenAI / Gemini)，可上传图片分析
- **视频分析** — MediaPipe 姿态识别，分析跑步姿态
- **赛事规划** — 基于近期成绩预测完赛时间，生成配速策略
- **数据导入** — CSV 多平台自动识别 (Garmin/Apple/华为/小米/Keep/悦跑圈)
- **每日打卡** — 训练日记、心情、体重记录

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12+ / FastAPI / SQLAlchemy / SQLite |
| 前端 | React 19 / TypeScript / Vite / Tailwind CSS 4 |
| 姿态分析 | MediaPipe / OpenCV |
| AI | Anthropic / OpenAI / DeepSeek / Gemini API |
| 打包 | PyInstaller (Windows 桌面端) |

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/yourname/stride.git
cd stride
```

### 2. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # macOS/Linux

# 国内用户建议先换清华源（mediapipe 等大包更快）
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制模板并填入凭据）
copy .env.example .env     # 编辑 .env 填入 COROS 账号和 AI API Key
```

### 3. 前端

```bash
cd frontend
npm install
npm run build              # 构建到 frontend/dist/
```

### 4. 启动

```bash
cd backend
python launcher.py         # 启动服务 + 自动打开浏览器
# 或手动: uvicorn main:app --host 0.0.0.0 --port 8000
```

访问 `http://localhost:8000`

### 5. 桌面打包 (可选)

```bash
pyinstaller pyinstaller.spec --clean --noconfirm
# 输出在 dist/RunningTrainer/
```

## 环境变量

在 `backend/.env` 中配置：

| 变量 | 必填 | 说明 |
|------|------|------|
| `COROS_EMAIL` | 推荐 | COROS 账号邮箱 |
| `COROS_PASSWORD` | 推荐 | COROS 账号密码 |
| `COROS_REGION` | 否 | COROS 区域 (cn/com)，默认 cn |
| `DEEPSEEK_API_KEY` | 否 | AI 教练 (DeepSeek) |
| `ANTHROPIC_API_KEY` | 否 | AI 教练 (Claude) |
| `OPENAI_API_KEY` | 否 | AI 教练 (GPT) |
| `GOOGLE_API_KEY` | 否 | AI 教练 (Gemini) |
| `SECRET_KEY` | 否 | 生产环境修改 |

## 目录结构

```
stride/
├── backend/              # FastAPI 后端
│   ├── main.py           # 应用入口
│   ├── launcher.py       # 桌面启动器 + 自检
│   ├── database.py       # 数据库模型与连接
│   ├── config.py         # 配置加载
│   ├── db/               # 数据库 ORM 模型
│   ├── routers/          # API 路由
│   └── services/         # 业务逻辑
├── frontend/             # React 前端
│   ├── src/
│   │   ├── pages/        # 页面组件
│   │   ├── components/   # 通用组件
│   │   └── services/     # API 调用
│   └── dist/             # 构建产物
├── activation_server/    # 激活码验证服务（可选）
├── pyinstaller.spec      # PyInstaller 打包配置
└── start.bat             # 一键构建+启动脚本
```

## 开源协议

[MIT](LICENSE)
