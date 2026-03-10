# Project Texas 🐺

*“任务完成。这就足够了，不是吗？” —— 德克萨斯*

Project Texas 是一个探索性的二次元游戏自动化代理框架。本项目以《明日方舟》干员德克萨斯命名，寓意其具备在复杂未知游戏场景中**冷静感知、高效规划、利落执行**的先锋能力。

## 目录结构

MaaTexas/          # Auto-Anime-Agent (A3) 
├── docs/              # 详细的架构图、API文档和设计文档
├── src/               # 核心源码目录
│   ├── perception/    # 感知层 (快流CV、慢流VLM、状态观测器)
│   ├── planning/      # 决策与规划层 (宏观LLM路由、微观状态机/行为树)
│   ├── control/       # 执行层 (基于 MaaFramework 的底层动作下发)
│   ├── core/          # 核心总线 (Agent 主循环、状态管理 World Model)
│   └── utils/         # 通用工具 (日志打点、配置解析、可视化等)
├── tests/             # 单元测试与集成测试 (刚才讨论的截图测试就放这)
├── config/            # 配置文件 (ODD定义、大模型 API Key、默认设备端口等)
├── requirements.txt   # 依赖清单
├── .gitignore         # Git 忽略文件
└── README.md          # 项目说明文档

## 🎯 核心愿景
突破传统基于静态模板和硬编码规则的流水线脚本限制，引入自动驾驶领域的 PnC (Perception, Planning, Control) 架构思想。结合大语言模型 (LLM) 和视觉大模型 (VLM)，打造一个能自主决策、自我纠错的泛用型 Game AI Agent。
## 🏗️ 架构设计
本项目采用**异构双流感知**与**分层规控**架构：

- **底层驱动 (Control)：** 依托 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 强大的跨设备底层接管与基础图像处理能力，作为系统的“线控底盘”。
- **快流感知 (System 1)：** 基于 OpenCV 和轻量级 OCR，进行高频 (10Hz+) 的 UI 元素提取和状态跟踪。
- **慢流感知 (System 2)：** 引入 VLM (如 Qwen-VL, GPT-4o) 结合 Set-of-Mark (SoM) 视觉提示，处理低频、长尾的复杂场景语义理解与异常接管。
- **分层决策 (Planning)：**
  - **宏观规划 (Macro)：** LLM 负责全局路由和任务链拆解。
  - **微观规划 (Micro)：** 状态机/行为树负责具体场景下的高频战术执行。

## 🗺️ 开发路线图 (Roadmap)

### Phase 1: 基础设施与单流验证 (当前阶段)
- [ ] 初始化工程结构。
- [ ] 跑通基于 MaaFramework 的 Python API，实现稳定的画面获取 (Sensor Feed) 单元测试。
- [ ] 实现基础快流：提取画面文字与 UI BBox，输出结构化 JSON 状态。
- [ ] 实现慢流验证：构建带有 BBox 编号的 Prompt，验证 VLM 的区域理解能力。

### Phase 2: 极简闭环构建 (MVP)
- [ ] 构建世界模型 (World Model)，融合双流感知数据。
- [ ] 实现 Agent 主循环：`感知 -> 状态更新 -> 宏观路由 -> 动作下发`。
- [ ] 完成一个简单的端到端测试用例（如：完全不依赖硬编码坐标，依靠 VLM 指引从主界面导航至特定二级页面）。

### Phase 3: 进阶规控与记忆
- [ ] 引入行为树处理高动态场景（如简单战斗）。
- [ ] 完善 ODD (设计运行域) 监控与 Fallback 异常接管机制。
- [ ] 建立 RAG 知识库，使 Agent 能动态查阅游戏图鉴或攻略。

## 🛠️ 快速开始
*(待完善：环境依赖安装与运行说明)*