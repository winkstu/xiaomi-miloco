# Xiaomi Miloco Code Wiki

## 项目概述

**Xiaomi Miloco** (小米本地Copilot) 是一个智能家居本地化AI解决方案，基于小米摄像头作为视觉信息源，配合自研的本地LLM，连接全屋IoT设备。用户可以通过自然语言定义各种家庭需求和规则，实现更广泛、更具创意的智能设备联动。

## 项目结构

```
/workspace/
├── miloco_server/          # 主服务端 - FastAPI应用
├── miloco_ai_engine/       # AI引擎 - 本地模型推理服务
├── miot_kit/               # 小米IoT设备通信SDK
├── web_ui/                 # React前端应用
├── third_party/            # 第三方依赖
│   └── llama.cpp/          # LLaMA.cpp推理框架
├── docker/                 # Docker配置
├── config/                 # 配置文件
├── scripts/                # 启动脚本
└── docs/                   # 文档
```

## 核心模块架构

### 1. miloco_server - 主服务端

主服务端采用分层架构，基于FastAPI构建。

#### 目录结构

```
miloco_server/
├── main.py                    # FastAPI应用入口
├── agent/                     # AI Agent模块
│   ├── chat_agent.py          # 对话Agent (ReAct模式)
│   ├── nlp_request_agent.py  # NLP请求处理
│   └── dynamic_execute_agent.py # 动态执行Agent
├── controller/                # 控制器层 (API路由)
│   ├── auth_controller.py     # 认证接口
│   ├── chat_controller.py     # 对话接口
│   ├── trigger_controller.py   # 触发规则接口
│   ├── mcp_controller.py      # MCP服务接口
│   ├── model_controller.py     # 模型配置接口
│   ├── miot_controller.py     # 小米IoT接口
│   └── ha_controller.py       # HomeAssistant接口
├── service/                   # 业务逻辑层
│   ├── manager.py             # 服务管理器 (单例)
│   ├── auth_service.py        # 认证服务
│   ├── chat_history_service.py # 聊天历史服务
│   ├── trigger_rule_service.py # 触发规则服务
│   ├── model_service.py       # 模型服务
│   ├── mcp_service.py         # MCP服务
│   ├── miot_service.py        # 小米IoT服务
│   └── ha_service.py          # HomeAssistant服务
├── dao/                       # 数据访问层
│   ├── kv_dao.py             # 键值存储
│   ├── trigger_dao.py         # 触发规则DAO
│   ├── chat_history_dao.py    # 聊天历史DAO
│   ├── mcp_config_dao.py      # MCP配置DAO
│   └── third_party_model_dao.py # 第三方模型DAO
├── proxy/                     # 代理层
│   ├── llm_proxy.py           # LLM调用代理
│   ├── miot_proxy.py          # 小米IoT代理
│   └── ha_proxy.py            # HomeAssistant代理
├── mcp/                       # MCP协议实现
│   ├── mcp_client.py          # MCP客户端基类
│   ├── mcp_client_manager.py  # MCP客户端管理器
│   ├── local_mcp_servers.py   # 本地MCP服务器
│   └── tool_executor.py       # 工具执行器
├── utils/                     # 工具模块
│   ├── llm_utils/             # LLM工具
│   │   ├── base_llm_util.py
│   │   ├── action_converter.py
│   │   ├── device_chooser.py
│   │   └── vision_understander.py
│   ├── database.py            # SQLite数据库连接器
│   ├── prompt_helper.py       # Prompt辅助
│   ├── trigger_filter.py      # 触发过滤
│   └── local_models.py        # 本地模型枚举
├── middleware/                # 中间件
│   ├── auth_middleware.py     # 认证中间件
│   └── exception_handler.py   # 异常处理
├── schema/                    # 数据模型
│   ├── chat_schema.py
│   ├── trigger_schema.py
│   ├── mcp_schema.py
│   └── ...
└── config/                    # 配置模块
    ├── config_loader.py
    └── prompt_config.py
```

#### 核心类与函数

##### Manager (服务管理器)

**位置**: `miloco_server/service/manager.py`

```python
class Manager:
    """服务管理器单例类"""
    
    # 服务访问属性
    @property
    def auth_service(self) -> AuthService
    @property
    def miot_service(self) -> MiotService
    @property
    def ha_service(self) -> HaService
    @property
    def trigger_rule_service(self) -> TriggerRuleService
    @property
    def model_service(self) -> ModelService
    @property
    def mcp_service(self) -> McpService
    @property
    def chat_service(self) -> ChatHistoryService
    @property
    def tool_executor(self) -> ToolExecutor
```

**职责**:
- 管理所有服务的初始化
- 提供服务访问接口
- 管理DAO层和Proxy层实例

##### ChatAgent (对话Agent)

**位置**: `miloco_server/agent/chat_agent.py`

```python
class ChatAgent(Actor):
    """ReAct Agent - 基于think-act-observe循环"""
    
    def __init__(self, request_id, out_actor_address, chat_history_messages)
    
    async def _run_chat(self, query: str) -> None
    async def _cyclic_execute(self) -> tuple[bool, str | None]
    async def _execute_step(self, step_number: int) -> Optional[str]
    async def _call_llm_stream(self) -> AsyncGenerator[dict, None]
    async def _execute_tools(self, tool_calls) -> None
```

**核心流程**:
1. 接收用户查询
2. 调用LLM生成响应
3. 检测工具调用
4. 执行工具
5. 返回最终答案

##### LLMProxy (LLM代理)

**位置**: `miloco_server/proxy/llm_proxy.py`

```python
class LLMProxy(ABC):
    """LLM代理抽象基类"""
    
    async def async_call_llm(self, messages, tools=None) -> dict
    async def async_call_llm_stream(self, messages, tools=None) -> AsyncGenerator[dict, None]

class OpenAIProxy(LLMProxy):
    """OpenAI兼容API代理"""
    def __init__(self, base_url: str, api_key: str, model_name: str)
```

##### ToolExecutor (工具执行器)

**位置**: `miloco_server/mcp/tool_executor.py`

```python
class ToolExecutor:
    """MCP工具执行器"""
    
    async def execute_tool_by_params(self, client_id, tool_name, parameters) -> CallToolResult
    def parse_tool_call(self, tool_call) -> tuple[str, str, dict]
    def get_mcp_chat_completion_tools(self, mcp_client_ids, exclude_tool_names=None) -> list
```

### 2. miloco_ai_engine - AI引擎

本地模型推理服务，管理AI模型的加载和请求处理。

#### 目录结构

```
miloco_ai_engine/
├── main.py                     # FastAPI应用入口
├── model_manager/              # 模型管理器
│   ├── model_manager.py        # 模型生命周期管理
│   └── model_wrapper.py        # 模型包装器 (Actor)
├── core_python/                # Python绑定层
│   ├── llama_mico.py           # LLaMA-MICO接口
│   └── lib_manager.py          # 动态库管理
├── task_scheduler/             # 任务调度器
│   ├── model_scheduler.py
│   └── scheduler_task.py
├── core/                       # C++核心 (llama-mico)
│   ├── llama-mico.cpp
│   ├── llama-mico.h
│   └── batch_scheduling/       # 批处理调度
├── config/                     # 配置
│   ├── config.py
│   ├── config_info.py
│   └── config_optimizer.py
├── schema/                     # 数据模型
│   ├── models_schema.py
│   └── actor_message.py
└── middleware/                 # 中间件
```

#### 核心类与函数

##### ModelManager (模型管理器)

**位置**: `miloco_ai_engine/model_manager/model_manager.py`

```python
class ModelManager:
    """模型管理器"""
    
    def __init__(self)
    async def start(self)
    async def stop(self)
    async def auto_load_model(self, model_name: str)
    async def auto_unload_model(self, model_name: str)
    async def chat_completions(self, model_name, request) -> ChatCompletionResponse
    async def chat_completions_stream(self, model_name, request) -> AsyncGenerator
    def model_list(self) -> List[str]
    def model_info(self, model_name: str) -> ModelInfo
    def model_desc(self, model_name: str) -> ModelDescription
    def get_vram_usage(self) -> VramUsage
```

**模型加载策略**:
```python
class ModelLoadStrategy(Enum):
    RESIDENT = "resident"    # 常驻内存
    ON_DEMAND = "on_demand"  # 按需加载 (未启用)
    ONLY_ONE = "only_one"    # 仅加载最后使用的模型
```

##### ModelWrapper (模型包装器)

**位置**: `miloco_ai_engine/model_manager/model_wrapper.py`

```python
class ModelWrapper(Actor):
    """模型Actor - 管理单个模型实例"""
    
    def receiveMessage(self, msg: RequestMessage, sender: ActorAddress)
    def _load(self) -> ResultMessage
    def _unload(self) -> ResultMessage
    async def _handle_chat(self, data, future)
    async def _handle_stream_chat(self, data, future)
```

**Actor消息类型**:
```python
class ModelAction(Enum):
    LOAD = "load"
    UNLOAD = "unload"
    CHAT = "chat"
    STREAM_CHAT = "stream_chat"
    GET_STATUS = "get_status"
    CLEANUP = "cleanup"
    CHAT_RESPONSE = "chat_response"
```

##### LlamaMico (核心推理接口)

**位置**: `miloco_ai_engine/core_python/llama_mico.py`

```python
class LlamaMico:
    """LLaMA-MICO核心接口"""
    
    def init(self, config: Dict[str, Any]) -> Optional[ctypes.c_void_p]
    def cleanup(self, handle: ctypes.c_void_p)
    def chat_completion(self, handle, messages, tools, priority=0, temperature=-1.0, stream=False)
```

**C API接口** (llama-mico.h):
```c
int32_t llama_mico_init(const char *config_json, void **handle);
int32_t llama_mico_free(void *handle);
int32_t llama_mico_request_prompt(void *handle, const char *request_json_str, 
                                   int32_t *is_finished, const char **content);
int32_t llama_mico_request_generate(void *handle, const char *request_json_str,
                                     int32_t *is_finished, const char **content);
```

### 3. miot_kit - 小米IoT SDK

设备通信SDK，支持小米IoT设备和HomeAssistant。

#### 目录结构

```
miot_kit/miot/
├── client.py              # MIoT客户端主类
├── mcp.py                 # MCP服务器实现
├── cloud.py               # 云端通信
├── lan.py                 # 局域网通信
├── camera.py              # 摄像头支持
├── ha_api.py              # HomeAssistant API
├── oauth2.py              # OAuth2认证
├── spec.py                # 设备规格解析
├── storage.py             # 本地存储
├── i18n.py                # 国际化
├── mcp.py                 # MCP协议实现
├── types.py               # 类型定义
├── const.py               # 常量定义
├── error.py               # 错误定义
└── configs/               # 配置文件
```

#### 核心类

##### MIoTClient

**位置**: `miot_kit/miot/client.py`

```python
class MIoTClient:
    """MIoT客户端"""
    
    async def init_async(self)
    async def deinit_async(self)
    async def gen_oauth_url_async(redirect_uri) -> str
    async def get_access_token_async(code, state) -> MIoTOauthInfo
    async def refresh_access_token_async(refresh_token) -> MIoTOauthInfo
    async def get_homes_async(fetch_share_home=False) -> Dict[str, MIoTHomeInfo]
    async def get_devices_async(home_list=None, fetch_share_home=False) -> Dict[str, MIoTDeviceInfo]
    async def get_cameras_async(home_list=None, fetch_share_home=False) -> Dict[str, MIoTCameraInfo]
    async def create_camera_instance_async(camera_info, frame_interval=500, enable_hw_accel=True) -> MIoTCameraInstance
```

##### MCP服务器

**位置**: `miot_kit/miot/mcp.py`

```python
class MIoTManualSceneMcp:
    """手动场景MCP服务器"""
    _TOOL_NAME_GET_SCENES = "get_manual_scenes"
    _TOOL_NAME_TRIGGER_SCENE = "trigger_manual_scene"
    _TOOL_NAME_SEND_NOTIFY = "send_app_notify"

class MIoTDeviceMcp:
    """设备控制MCP服务器"""
    _TOOL_NAME_GET_DEVICES = "get_devices"
    _TOOL_NAME_GET_DEVICE_SPEC = "get_device_spec"
    _TOOL_NAME_SEND_CTRL_RPC = "send_ctrl_rpc"
    _TOOL_NAME_SEND_GET_RPC = "send_get_rpc"

class HomeAssistantAutomationMcp:
    """HomeAssistant自动化MCP服务器"""
    _TOOL_NAME_GET_AUTOMATIONS = "get_automations"
    _TOOL_NAME_TRIGGER_AUTOMATION = "trigger_automation"
```

### 4. web_ui - React前端

前端应用基于React + Ant Design构建。

#### 目录结构

```
web_ui/
├── src/
│   ├── App.jsx               # 主应用组件
│   ├── api/
│   │   └── index.js         # API调用
│   ├── components/          # UI组件
│   │   ├── Header/
│   │   ├── MessageRenderer/  # 消息渲染
│   │   │   ├── AiGeneratedActionsMessage/
│   │   │   ├── CameraImagesMessage/
│   │   │   ├── FinalAnswerContent/
│   │   │   └── ...
│   │   └── ...
│   └── assets/
├── package.json
└── config.js
```

#### 主要依赖

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "antd": "^5.21.0",
    "@ant-design/x": "^1.5.0",
    "axios": "^1.12.0",
    "react-router-dom": "^6.17.0",
    "zustand": "^5.0.8",
    "i18next": "^25.3.2",
    "hls.js": "^1.6.5"
  }
}
```

## 模块间依赖关系

```
┌─────────────────────────────────────────────────────────────┐
│                        Web UI (React)                        │
│                     WebSocket / REST API                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   miloco_server (FastAPI)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Controller│  │ Service  │  │  Proxy   │  │   MCP    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │   DAO    │  │  Agent   │  │  Utils   │                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  miot_kit    │  │  miloco_ai_engine │  │   第三方API       │
│  (设备通信)   │  │    (模型推理)     │  │   (OpenAI等)     │
└──────────────┘  └──────────────────┘  └──────────────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │    llama.cpp     │
                 │   (C++推理框架)   │
                 └──────────────────┘
```

## 数据库表结构

**位置**: `miloco_server/utils/database.py`

### 表清单

| 表名 | 描述 |
|------|------|
| kv | 键值存储 |
| trigger_rule | 触发规则 |
| trigger_rule_log | 触发规则执行日志 |
| model_vendor | 第三方模型配置 |
| chat_history | 聊天历史 |
| mcp_config | MCP服务配置 |

### 主要表结构

```sql
-- 触发规则表
CREATE TABLE trigger_rule (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    enabled BOOLEAN DEFAULT 1,
    camera_dids TEXT NOT NULL,  -- JSON
    condition TEXT NOT NULL,
    execute_info TEXT,
    filter TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 聊天历史表
CREATE TABLE chat_history (
    session_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    messages TEXT,  -- JSON
    session TEXT,  -- JSON
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- MCP配置表
CREATE TABLE mcp_config (
    id TEXT PRIMARY KEY,
    access_type TEXT NOT NULL,  -- http_sse, streamable_http, stdio
    name TEXT NOT NULL,
    url TEXT,
    command TEXT,
    args TEXT,  -- JSON
    env_vars TEXT,  -- JSON
    enable BOOLEAN DEFAULT 1,
    timeout INTEGER DEFAULT 60
);
```

## Docker部署架构

**位置**: `docker/docker-compose.yaml`

```yaml
services:
  ai_engine:
    container_name: miloco-ai_engine
    image: xiaomi/miloco-ai_engine:latest
    ports:
      - 8001:8001
    volumes:
      - ./models:/models
      - ./log/ai_engine:/app/.log/ai_engine
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  backend:
    container_name: miloco-backend
    image: xiaomi/miloco-backend:latest
    network_mode: host
    ports:
      - 8000:8000
    volumes:
      - ./data:/app/miloco_server/.temp
      - ./log/backend:/app/miloco_server/.temp/log
```

## 运行方式

### 1. Docker部署 (推荐)

```bash
# 一键安装
bash -c "$(wget -qO- https://xiaomi-miloco.cnbj1.mi-fds.com/xiaomi-miloco/install.sh)"

# 或克隆源码后安装
git clone https://github.com/XiaoMi/xiaomi-miloco.git
bash scripts/install.sh
```

### 2. 源码运行

#### AI引擎

```bash
cd miloco_ai_engine
pip install -e .
python -m miloco_ai_engine.main
```

#### 主服务

```bash
cd miloco_server
pip install -e .
python -m miloco_server.main
```

### 3. 启动脚本

```bash
# 启动AI引擎
python scripts/start_ai_engine.py

# 启动主服务
python scripts/start_server.py
```

## 配置说明

### AI引擎配置

**位置**: `config/ai_engine_config.yaml`

```yaml
models:
  miloco-vl:
    model_path: "/models/miloco-vl.gguf"
    mmproj_path: "/models/mmproj.gguf"
    total_context_num: 32768
    chunk_size: 1024
    n_gpu_layers: 50
```

### 服务配置

**位置**: `config/server_config.yaml`

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  log_level: "info"
```

### Prompt配置

**位置**: `config/prompt_config.yaml`

定义不同场景下的系统提示词。

## MCP协议支持

### 支持的传输类型

| 类型 | 说明 |
|------|------|
| LOCAL | 本地MCP服务器 (同进程) |
| STDIO | 标准输入输出通信 |
| HTTP_SSE | HTTP Server-Sent Events |
| STREAMABLE_HTTP | Streamable HTTP |

### 本地MCP服务

- **MIoTManualSceneMcp**: 小米手动场景
- **MIoTDeviceMcp**: 设备控制
- **HomeAssistantAutomationMcp**: HomeAssistant自动化

## 系统要求

### 硬件要求

- CPU: x64架构
- GPU: NVIDIA 30系列及以上，8GB显存 (推荐12GB+)
- 存储: 推荐16GB以上可用空间

### 软件要求

- 操作系统: Linux (Ubuntu 22.04+), Windows (WSL2), macOS (不支持)
- Docker: 20.10+
- NVIDIA Driver + CUDA支持
- NVIDIA Container Toolkit

## 技术栈

### 后端

- **框架**: FastAPI
- **并发**: Thespian Actor
- **数据库**: SQLite
- **AI推理**: llama.cpp

### 前端

- **框架**: React 18
- **UI库**: Ant Design 5
- **状态管理**: Zustand
- **构建工具**: Vite

### 通信

- **REST API**: FastAPI
- **WebSocket**: 实时对话
- **MCP**: Model Context Protocol

## 版本信息

- 项目版本: 详见 `VERSION` 文件
- Python要求: >= 3.11
- 依赖管理: Poetry / pip
