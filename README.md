# 智慧文旅与交通建设

> 广州市白云区智慧文旅智能问答平台 —— 基于知识图谱 + DeepSeek RAG 的文旅智能问答与路线规划系统

---

## 目录

- [一、项目简介](#一项目简介)
- [二、技术栈](#二技术栈)
- [三、项目结构](#三项目结构)
- [四、环境准备](#四环境准备)
- [五、配置说明 (.env)](#五配置说明-env)
- [六、启动方式](#六启动方式)
- [七、功能页面使用说明](#七功能页面使用说明)
- [八、API 接口文档](#八api-接口文档)
- [九、测试](#九测试)
- [十、故障排查](#十故障排查)
- [十一、部署](#十一部署)

---

## 一、项目简介

本项目是面向广州市白云区的智慧文旅平台，整合了区内 18 类文旅数据（景区、非遗、图书馆、酒店、充电站等，共 4257+ 条记录），构建了包含 **2469 个实体、2468 条关系**的知识图谱，结合 DeepSeek 大语言模型与混合检索（关键词 + 向量 + 图谱），提供智能问答、路线规划、文旅探索、3D 地图可视化等功能。

### 核心能力

| 能力 | 说明 |
|------|------|
| 智能问答 | DeepSeek + 知识图谱 RAG，支持自然语言提问 |
| 文旅探索 | 13 类实体检索、AI 增强详情、附近推荐 |
| 路线规划 | 基于图谱关系的游览路线智能规划 |
| 知识图谱 | 可视化网络图（ECharts 力导向布局） |
| 3D 地图 | 白云区地标 Three.js 三维渲染 |
| 智能体路由 | 4 个专业 Agent（文化传承/行程规划/附近推荐/通用问答） |
| 用户系统 | JWT 鉴权、会话历史、收藏管理 |

---

## 二、技术栈

### 后端
- **框架**: Flask 3.0 + SQLAlchemy 2.0 + Alembic
- **鉴权**: Flask-JWT-Extended (JWT)
- **限流**: Flask-Limiter + Redis
- **API 文档**: Flasgger (Swagger UI)
- **中文分词**: jieba
- **知识图谱**: networkx
- **向量检索**: sentence-transformers (BAAI/bge-small-zh-v1.5, dim=512)
- **LLM**: DeepSeek API (deepseek-chat) + Ollama 本地回退
- **缓存**: Redis (可选，未装自动降级内存缓存)
- **异步**: Celery (可选)

### 前端
- **框架**: Vue 3.5 + TypeScript + Composition API
- **构建**: Vite 6
- **状态**: Pinia
- **路由**: Vue Router 4
- **可视化**: ECharts 5 (图谱) + Three.js (3D 地图)

### 数据
- **数据库**: SQLite (开发) / PostgreSQL + pgvector (生产)
- **数据源**: 18 个 Excel 文件 (白云区真实文旅数据)

---

## 三、项目结构

```
智慧文旅与交通建设/
├── backend/                    # 后端
│   ├── app.py                  # Flask 主应用 (37 个 API 端点)
│   ├── config.py               # 配置读取
│   ├── rag_engine.py           # RAG 引擎 (混合检索 + LLM)
│   ├── knowledge_graph.py      # 知识图谱构建与查询
│   ├── route_planner.py        # 路线规划
│   ├── agent_engine.py         # 智能体编排
│   ├── recommendation.py       # 推荐引擎
│   ├── vector_store.py         # 向量存储
│   ├── data_cleaner.py         # 数据清洗
│   ├── auth.py                 # JWT 鉴权
│   ├── models.py               # 数据库模型
│   ├── database.py             # 数据库连接
│   ├── routes/                 # 蓝图模块
│   │   ├── history.py          # 会话历史
│   │   ├── favorites.py        # 收藏管理
│   │   ├── feedback.py         # 问答反馈
│   │   ├── map3d.py            # 3D 地图
│   │   └── admin.py            # 管理后台
│   ├── graph_data/             # 图谱缓存 (graphml + 向量索引)
│   ├── tests/                  # 测试
│   │   ├── sandbox_test.py     # 全功能沙盒测试 (75 用例)
│   │   └── test_*.py           # 单元测试
│   └── requirements.txt
├── frontend/                   # 前端
│   ├── src/
│   │   ├── views/              # 8 个页面
│   │   ├── api/                # API 调用层
│   │   ├── components/         # 组件 (含 3D 引擎)
│   │   ├── composables/        # 组合式函数
│   │   ├── stores/             # Pinia 状态
│   │   └── constants/          # 端点/配置常量
│   ├── vite.config.ts
│   └── package.json
├── 智慧文旅与交通建设数据/       # 18 个 Excel 数据源
├── deploy/                     # 部署配置 (gunicorn/nginx/supervisor)
├── .env                        # 环境变量 (需配置)
├── .env.example                # 环境变量模板
├── start.ps1                   # Windows 一键启动 (PowerShell)
├── start.bat                   # Windows 一键启动 (CMD)
├── docker-compose.yml          # Docker 编排
└── Dockerfile
```

---

## 四、环境准备

### 必备软件

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10+ (推荐 3.12) | 后端运行时 |
| Node.js | 18+ | 前端构建 |
| npm | 随 Node 安装 | 前端包管理 |
| Redis | 6+ (可选) | 缓存；未安装自动降级为内存缓存 |
| PostgreSQL | 15+ (可选) | 生产数据库；开发默认用 SQLite |

### 安装步骤

1. **克隆/进入项目目录**
   ```powershell
   cd F:\project\智慧文旅与交通建设
   ```

2. **配置环境变量**（详见 [第五节](#五配置说明-env)）
   ```powershell
   copy .env.example .env
   # 编辑 .env 填写真实值
   ```

3. **安装后端依赖**
   ```powershell
   cd backend
   pip install -r requirements.txt --no-cache-dir
   ```

4. **安装前端依赖**
   ```powershell
   cd frontend
   npm install
   ```

---

## 五、配置说明 (.env)

复制 `.env.example` 为 `.env`，按需填写。关键配置项：

### 必须配置

```ini
# 安全密钥 (32 位随机字符串，生产环境必须修改)
SECRET_KEY=your-32-char-random-string
JWT_SECRET_KEY=another-32-char-random-string

# DeepSeek API (不配置则降级为本地知识图谱问答)
DEEPSEEK_API_KEY=sk-你的真实密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com/chat/completions
DEEPSEEK_MODEL=deepseek-chat
```

### 数据库

```ini
# 开发环境 (SQLite，无需额外安装)
DATABASE_URL=sqlite:///baiyun_culture.db

# 生产环境 (PostgreSQL)
# DATABASE_URL=postgresql+psycopg2://baiyun:密码@localhost:5432/baiyun_culture
```

### 可选配置

```ini
AMAP_KEY=你的高德地图密钥              # 实时 POI/天气 (可选)
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5 # 嵌入模型 (留空则用 TF-IDF 降级)
OLLAMA_ENABLED=false                   # Ollama 本地 LLM 回退
CACHE_ENABLED=true                     # Redis 缓存
RATE_LIMIT_ENABLED=true                # API 限流
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5000  # CORS 白名单
```

### 功能开关

```ini
ENABLE_AGENTS=true           # 智能体路由
ENABLE_HYBRID_SEARCH=true    # 混合检索
ENABLE_RECOMMENDATION=true   # 推荐系统
ENABLE_REALTIME_DATA=false   # 实时数据 (需高德 API)
ENABLE_EVALUATION=false      # 评估系统
```

> **DeepSeek API 状态检测**：后端启动时会检测 API Key 是否为占位符（如 `sk-your-...`）。若为占位符，自动降级为本地知识图谱模式，前端会显示提示横幅。

---

## 六、启动方式

### 方式 A：一键启动（推荐）

#### Windows (PowerShell)
```powershell
.\start.ps1
```

#### Windows (CMD)
```cmd
start.bat
```

脚本自动完成 5 个步骤：
1. 清理环境
2. 安装 Python 依赖
3. 初始化数据库 (`init_db.py`)
4. 构建前端 (`vite build`)
5. 启动 Flask 服务

启动后访问 **http://localhost:5000**。

### 方式 B：开发模式（前后端分离，支持热更新）

**终端 1 — 后端：**
```powershell
cd backend
python init_db.py    # 仅首次运行
python app.py        # 启动 Flask，监听 5000
```

**终端 2 — 前端：**
```powershell
cd frontend
npm run dev          # Vite 开发服务器，监听 3000
```

开发模式访问 **http://localhost:3000**（前端通过 Vite 代理转发 API 请求到 5000）。

### 方式 C：Docker Compose（生产部署）

```powershell
docker-compose up -d
```

拉起三个容器：
- **PostgreSQL** (pgvector) — 端口 5432
- **Redis** — 端口 6379
- **Flask 应用** — 端口 5000

访问 **http://localhost:5000**。

### 启动验证

| 检查项 | 地址 |
|--------|------|
| 应用首页 | http://localhost:5000 |
| 健康检查 | http://localhost:5000/api/health |
| API 文档 | http://localhost:5000/api/docs/ |

健康检查预期返回（关键字段）：
```json
{
  "status": "ok",
  "database": "ok",
  "llm_enabled": true,
  "llm_provider": "deepseek",
  "knowledge_graph": {"entities": 2469, "relations": 2468}
}
```

---

## 七、功能页面使用说明

启动后打开 Web 界面，共 8 个功能页面：

### 1. 智能问答 (`/`)
**无需登录。** 核心功能页面。
- 在输入框输入自然语言问题，如"白云山有什么历史？""三元里有哪些非遗项目？"
- 系统通过混合检索（关键词+向量+图谱）+ DeepSeek 生成回答
- 回答下方显示相关实体和来源
- 支持 4 个智能体自动路由：文化传承 / 行程规划 / 附近推荐 / 通用问答

### 2. 文旅探索 (`/explore`)
**无需登录。**
- 左侧选择分类（13 类：景点、公园、非遗、图书馆、酒店等）
- 点击实体查看增强详情（含 AI 描述、附近推荐、关系子图）
- 使用"路线规划"输入起点，生成游览路线
- 使用"AI 搜索"进行语义搜索

### 3. 知识图谱 (`/graph`)
**无需登录。**
- 搜索实体 → 查看实体详情（类型、关系、属性）
- 可视化网络图（ECharts 力导向布局，50 节点 + 55 边）
- 查看图谱统计（2469 实体 / 2468 关系）

### 4. 3D 地图 (`/map3d`)
**无需登录。** 需要支持 WebGL 的浏览器。
- 白云区地标建筑的 3D 渲染（Three.js）
- 建筑模块、道路网络、LOD 层级管理

### 5. 数据统计 (`/stats`)
**无需登录。**
- 文旅数据统计概览
- 位置频次分布图表
- 实体类型分布

### 6. 历史会话 (`/history`)
**需要登录。** 未登录自动跳转问答页。
- 查看历史问答记录
- 按会话查看消息详情

### 7. 我的收藏 (`/favorites`)
**需要登录。** 未登录自动跳转问答页。
- 收藏感兴趣的实体
- 管理收藏列表（添加/删除）

### 8. 关于 (`/about`)
项目介绍页面。

### 用户注册与登录

点击页面右上角"登录"按钮：
1. **注册**：填写用户名、邮箱、密码
2. **登录**：输入用户名 + 密码，获取 JWT token
3. 登录后可访问"历史会话"和"我的收藏"页面

---

## 八、API 接口文档

### Swagger UI

启动后端后访问 **http://localhost:5000/api/docs/** 查看交互式 API 文档。

### 主要接口列表

#### 系统
| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/health` | 健康检查 | 否 |
| GET | `/api/notice` | 系统公告 | 否 |

#### 智能问答
| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/qa` | 智能问答（非流式） | 否 |
| POST | `/api/qa/stream` | 流式问答 (SSE) | 否 |
| POST | `/api/v2/qa` | V2 智能问答（含智能体路由） | 否 |
| GET | `/api/v2/agents` | 获取智能体列表 | 否 |
| GET | `/api/v2/recommend` | 推荐系统 | 否 |
| GET | `/api/hot-questions` | 热门问题 | 否 |

#### 知识图谱
| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/graph/stats` | 图谱统计 | 否 |
| GET | `/api/graph/search?q=&top_k=` | 实体搜索 | 否 |
| GET | `/api/graph/entity/<name>` | 实体详情 | 否 |
| GET | `/api/graph/entities?type=&limit=` | 按类型查实体 | 否 |
| GET | `/api/graph/visualization` | 图谱可视化数据 | 否 |

#### 文旅探索
| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/data/categories` | 分类列表 | 否 |
| GET | `/api/explore/entity/<name>/enhanced` | 增强详情 | 否 |
| GET | `/api/explore/entity/<name>/nearby` | 附近实体 | 否 |
| GET | `/api/explore/entity/<name>/context` | 实体上下文 | 否 |
| POST | `/api/explore/ai-search` | AI 搜索 | 否 |
| POST | `/api/explore/route-plan` | 路线规划 | 否 |

#### 地图
| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/map/coordinates?limit=` | 地标坐标 | 否 |
| GET | `/api/map/3d/config` | 3D 地图配置 | 否 |
| GET | `/api/map/3d/entities` | 3D 地图实体 | 否 |

#### 统计
| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/stats/overview` | 统计概览 | 否 |
| GET | `/api/stats/location-frequency` | 位置频次 | 否 |

#### 用户认证
| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/auth/register` | 注册 | 否 |
| POST | `/api/auth/login` | 登录 | 否 |
| POST | `/api/auth/refresh` | 刷新 token | 是 |
| GET | `/api/auth/me` | 当前用户信息 | 是 |
| POST | `/api/auth/logout` | 登出 | 是 |

#### 会话历史与收藏（需登录）
| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET | `/api/v2/sessions` | 会话列表 | 是 |
| GET | `/api/v2/sessions/<id>` | 会话详情 | 是 |
| GET | `/api/v2/favorites` | 收藏列表 | 是 |
| POST | `/api/v2/favorites` | 添加收藏 | 是 |
| DELETE | `/api/v2/favorites` | 删除收藏 | 是 |

### 调用示例

#### 智能问答
```bash
curl -X POST http://localhost:5000/api/qa \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"白云山有哪些景点？\"}"
```

#### 知识图谱搜索
```bash
curl "http://localhost:5000/api/graph/search?q=白云山&top_k=5"
```

#### 路线规划
```bash
curl -X POST http://localhost:5000/api/explore/route-plan \
  -H "Content-Type: application/json" \
  -d "{\"start\": \"白云山风景名胜区\", \"preferences\": [\"文化体验\"]}"
```

#### 注册并登录（鉴权接口示例）
```bash
# 1. 注册
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"test\",\"email\":\"test@test.com\",\"password\":\"Test1234!\"}"

# 2. 登录获取 token
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"test\",\"password\":\"Test1234!\"}"
# 返回: {"access_token": "eyJ...", "refresh_token": "..."}

# 3. 携带 token 请求鉴权接口
curl http://localhost:5000/api/v2/favorites \
  -H "Authorization: Bearer eyJ..."
```

---

## 九、测试

### 全功能沙盒测试（推荐）

覆盖 9 个模块、75 个测试用例，验证所有功能模块的核心逻辑、组件交互、数据流程和异常处理。

```powershell
cd backend
python tests/sandbox_test.py
```

**测试模块：**
1. 系统健康检查 + LLM 状态
2. 智能问答（含 fallback 异常处理）
3. 智能体路由 + 推荐系统
4. 知识图谱检索（搜索/实体/可视化/统计）
5. 文旅探索（分类/实体详情/附近/AI 搜索）
6. 路线规划 + 地图坐标
7. 历史会话 + 收藏管理（含 JWT 鉴权）
8. 数据统计 + 3D 地图配置
9. 异常处理（无效输入/不存在的实体）

**预期结果：75 通过 / 0 失败**，测试报告输出到 `tests/_sandbox_report.json`。

### 单元测试

```powershell
cd backend
python -m pytest tests/ -v
```

### 前端构建测试

```powershell
cd frontend
npm run build
```

---

## 十、故障排查

### 1. 启动报错 `ModuleNotFoundError`

**原因**：Python 依赖未安装。

**解决**：
```powershell
cd backend
pip install -r requirements.txt --no-cache-dir
```

### 2. `start.ps1` 在安装依赖步骤失败

**原因**：pip 缓存损坏（`Cache entry deserialization failed`）。

**解决**：
```powershell
pip cache purge
pip install -r backend/requirements.txt --no-cache-dir
```

### 3. 前端页面空白 / API 报错

**原因**：后端未启动，或端口被占用。

**解决**：
```powershell
# 检查后端是否运行
curl http://localhost:5000/api/health

# 检查端口占用
Get-NetTCPConnection -LocalPort 5000 -State Listen

# 如被占用，结束进程
Stop-Process -Id <PID> -Force
```

### 4. 智能问答回答是结构化数据，不是自然语言

**原因**：`.env` 中 `DEEPSEEK_API_KEY` 是占位符（`sk-your-...`）。

**解决**：
1. 编辑 `.env`，填写真实 DeepSeek API Key
2. 重启后端
3. 访问 `/api/health` 确认 `llm_enabled: true`

### 5. 收藏/历史页面 401 Unauthorized

**原因**：需要先登录获取 JWT token。

**解决**：点击右上角"登录"，注册账号并登录后访问。

### 6. 知识图谱首次加载慢

**原因**：首次启动需要从 Excel 数据构建知识图谱（约 1 分钟）。

**说明**：构建完成后缓存到 `backend/graph_data/`，后续启动从缓存加载（秒级）。

### 7. PowerShell 中文乱码

**解决**：
```powershell
$env:PYTHONIOENCODING="utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### 8. 3D 地图不显示

**原因**：浏览器不支持 WebGL，或显卡驱动过旧。

**解决**：使用 Chrome/Edge/Firefox 最新版本，确保启用硬件加速。

### 9. 数据库初始化失败

**原因**：数据库文件被占用或权限不足。

**解决**：
```powershell
# 删除旧数据库重新初始化
Remove-Item backend\baiyun_culture.db -ErrorAction SilentlyContinue
cd backend
python init_db.py
```

---

## 十一、部署

### 生产环境部署 (Docker)

```powershell
# 1. 配置 .env (务必修改密钥和数据库密码)
# 2. 启动
docker-compose up -d

# 3. 查看日志
docker-compose logs -f app

# 4. 停止
docker-compose down
```

### 生产环境部署 (裸机)

使用 [deploy/](deploy/) 目录下的配置：

```powershell
# 1. 安装 gunicorn
pip install gunicorn

# 2. 用 gunicorn 启动 (推荐多 worker)
cd backend
gunicorn -c ../deploy/gunicorn.conf.py "app:create_app()"

# 3. 配置 nginx 反向代理 (参考 deploy/nginx.conf)
# 4. 配置 supervisor 进程守护 (参考 deploy/supervisor.conf)
```

### 生产环境检查清单

- [ ] `.env` 中 `SECRET_KEY` 和 `JWT_SECRET_KEY` 已改为强随机字符串
- [ ] `DEEPSEEK_API_KEY` 已配置真实密钥
- [ ] `DATABASE_URL` 已切换为 PostgreSQL
- [ ] `ALLOWED_ORIGINS` 已改为生产域名
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] Redis 已启动并配置
- [ ] HTTPS 已配置 (nginx + SSL)
- [ ] 前端已构建 (`npm run build`)

---

## 相关文档

| 文档 | 说明 |
|------|------|
| `.env.example` | 环境变量配置模板 |
| `答辩PPT大纲.md` | 项目答辩 PPT 大纲 |
| `演示视频脚本.md` | 演示视频拍摄脚本 |
| `1-项目申报书.docx` | 项目申报书 |
| `2-方案核心内容.docx` | 技术方案核心内容 |
| `3-数据产品模型.docx` | 数据产品模型 |
| `4-实施路线图.docx` | 实施路线图 |

---

## 技术支持

如遇到问题，请按以下顺序排查：
1. 查看本指南 [第十节：故障排查](#十故障排查)
2. 运行沙盒测试 `python tests/sandbox_test.py` 定位问题
3. 查看后端日志（控制台输出）
4. 访问 `/api/health` 检查系统状态
5. 访问 `/api/docs/` 查看 API 文档

---

## License

本项目采用 **MIT 许可证** — 详见 [LICENSE](./LICENSE)。

### 商用说明

- 本项目允许商业使用，但需保留原始版权声明和 MIT 许可证文本
- 本项目维护者不对商用使用中的任何直接或间接损失承担责任
- 详见 [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) 中的商用说明章节

### 不可滥用声明

本项目的代码和资源**仅可用于合法、正当的目的**。详见 [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) 中的不可滥用声明章节。

### 免责声明

本软件按"原样"提供，不附带任何明示或暗示的担保。在适用法律允许的最大范围内，作者或版权持有人不对因使用本软件而产生的任何索赔、损害或其他责任负责。

### 贡献者

如果你想参与贡献，请阅读 [CONTRIBUTING.md](./CONTRIBUTING.md) 和 [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)。
