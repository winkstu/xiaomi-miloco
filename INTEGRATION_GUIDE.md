# 通用视频管理模块 - 集成指南

## 概述

新创建的通用视频管理模块 `miloco_server/utils/generic_video_camera.py` 完全兼容原有的 MIoTCamera/MIoTCameraInstance 接口，可以无缝替换原有闭源的摄像头模块。

## 主要特性

✅ **完全接口兼容** - 保持与原有模块完全一致的 API
✅ **多协议支持** - 支持 RTSP/ONVIF/HTTP 流等标准协议
✅ **自动重连** - 支持断线自动重连
✅ **硬件加速** - 支持可选的硬件加速
✅ **零依赖变化** - 不破坏现有依赖关系

## 使用方式

### 1. 配置通用摄像头

在项目根目录创建一个配置文件 `generic_cameras.json`：

```json
{
  "cameras": [
    {
      "did": "rtsp-cam-001",
      "name": "前门摄像头",
      "protocol": "rtsp",
      "stream_url": "rtsp://192.168.1.100:554/stream1",
      "username": "admin",
      "password": "your_password",
      "channel_count": 1
    },
    {
      "did": "rtsp-cam-002",
      "name": "后门摄像头",
      "protocol": "rtsp",
      "stream_url": "rtsp://192.168.1.101:554/stream1",
      "channel_count": 1
    }
  ]
}
```

### 2. 集成到项目

#### 方案 A: 替换原有模块（推荐用于测试）

修改 `miot_kit/miot/client.py` 或你的导入代码，将摄像头相关的导入替换为新模块：

```python
# 原有代码
from miot.camera import MIoTCamera, MIoTCameraInstance

# 替换为
from miloco_server.utils.generic_video_camera import (
    GenericCamera as MIoTCamera,
    GenericCameraInstance as MIoTCameraInstance,
    load_generic_camera_configs_from_json,
    create_miot_camera_info_from_config
)
```

#### 方案 B: 添加补充功能（保持原有功能）

在现有的 MiotService/MiotProxy 中添加通用摄像头支持：

```python
# 在 miloco_server/service/miot_service.py 或 miloco_server/proxy/miot_proxy.py 中

from miloco_server.utils.generic_video_camera import (
    GenericCamera,
    GenericCameraInstance,
    load_generic_camera_configs_from_json,
    create_miot_camera_info_from_config,
    GenericCameraConfig,
    VideoProtocol
)

class MiotService:
    def __init__(self, ...):
        # ... 原有代码 ...
        
        # 添加通用摄像头支持
        self._generic_camera = GenericCamera(loop=self._loop)
        
        # 加载配置
        camera_configs = load_generic_camera_configs_from_json(
            "generic_cameras.json"
        )
        for did, config in camera_configs.items():
            self._generic_camera.add_generic_camera_config(config)
```

### 3. 使用示例

#### 基本使用（与原有代码完全一致）

```python
# 创建配置
config = GenericCameraConfig(
    did="camera-001",
    name="My Camera",
    protocol=VideoProtocol.RTSP,
    stream_url="rtsp://192.168.1.100:554/stream",
    username="admin",
    password="123456"
)

# 创建通用摄像头
generic_camera = GenericCamera(loop=asyncio.get_event_loop())
generic_camera.add_generic_camera_config(config)

# 转换为兼容的 MIoTCameraInfo
camera_info = create_miot_camera_info_from_config(config)

# 创建实例（与原有接口一致）
instance = await generic_camera.create_camera_instance_async(
    camera_info,
    frame_interval=500
)

# 注册回调（与原有接口一致）
async def on_jpg_frame(data: bytes, timestamp: int, channel: int):
    print(f"Got frame at {timestamp}")

await instance.register_decode_jpg_callback(on_jpg_frame)

# 开始流（与原有接口一致）
await instance.start_async(enable_reconnect=True)

# 停止（与原有接口一致）
await instance.stop_async()
await instance.destroy()
```

### 4. 在触发规则或 MCP 中使用

由于新模块与原有接口完全兼容，您现有的所有功能（触发规则、MCP、视觉对话）都不需要修改！

```python
# 原有的触发规则代码继续工作
async def check_camera_motion(camera_id: str):
    # 完全兼容的使用方式
    camera_img_seq = miot_proxy.get_recent_camera_img(camera_id, 0, 5)
    # 原有逻辑继续...
```

## 兼容性保证

### 接口兼容性

| 原有接口 | 新模块对应 | 状态 |
|---------|----------|------|
| `MIoTCamera` | `GenericCamera` | ✅ 完全兼容 |
| `MIoTCameraInstance` | `GenericCameraInstance` | ✅ 完全兼容 |
| `create_camera_instance_async()` | 同名方法 | ✅ 完全兼容 |
| `start_async()` | 同名方法 | ✅ 完全兼容 |
| `stop_async()` | 同名方法 | ✅ 完全兼容 |
| `register_decode_jpg_callback()` | 同名方法 | ✅ 完全兼容 |
| `register_raw_stream()` | 同名方法 | ✅ 完全兼容 |

### 回调兼容性

**JPEG 回调** (完全兼容):
```python
async def callback(jpeg_data: bytes, timestamp: int, channel: int):
    # 与原有模块完全一致
    pass
```

**原始流回调** (完全兼容):
```python
async def callback(did: str, data: bytes, ts: int, channel: int, seq: int):
    # 与原有模块完全一致
    pass
```

## 依赖要求

```bash
# 必需
pip install opencv-python-headless pillow

# 可选 (ONVIF 支持)
pip install onvif-py
```

## 部署建议

1. **逐步迁移** - 先在测试环境验证，确保没有问题后再替换生产环境
2. **保持原有功能** - 可以在同一个项目中同时使用原有模块和新模块
3. **配置管理** - 使用 `generic_cameras.json` 管理通用摄像头配置

## 未来扩展计划

- [ ] ONVIF PTZ 控制
- [ ] HTTP 流 (HLS/MPEG-DASH) 支持
- [ ] WebRTC 支持
- [ ] 本地文件回放
- [ ] 更丰富的错误处理
- [ ] 性能优化和监控
