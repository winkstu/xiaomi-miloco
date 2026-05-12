# Copyright (C) 2025
# Universal Video Management Module
# 开源通用视频管理模块 - 支持 RTSP/ONVIF

"""
通用视频管理模块
支持多种视频源协议，提供统一的视频流处理接口

支持的协议:
- RTSP (Real Time Streaming Protocol)
- ONVIF (Open Network Video Interface Forum)
- HTTP/HTTPS 流 (HLS, MPEG-DASH)
- 本地文件

依赖:
    pip install opencv-python-headless aiortp av
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from pathlib import Path
import uuid
import queue
import numpy as np
from PIL import Image
import io

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("OpenCV not available, video decoding will be limited")

logger = logging.getLogger(__name__)


class VideoProtocol(Enum):
    """支持的视频协议"""
    RTSP = "rtsp"
    ONVIF = "onvif"
    HLS = "hls"
    HTTP_STREAM = "http_stream"
    LOCAL_FILE = "local_file"


class VideoCodec(Enum):
    """视频编解码格式"""
    H264 = "h264"
    H265 = "h265"
    MJPEG = "mjpeg"
    UNKNOWN = "unknown"


@dataclass
class VideoFrame:
    """视频帧数据结构"""
    data: bytes
    timestamp: int
    sequence: int
    width: int
    height: int
    codec: VideoCodec
    is_keyframe: bool = False
    channel: int = 0


@dataclass
class CameraConfig:
    """摄像头配置"""
    name: str
    stream_url: str
    protocol: VideoProtocol
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 30
    retry_interval: int = 5
    max_retries: int = 3
    frame_interval: int = 500  # ms
    auto_reconnect: bool = True
    enable_audio: bool = False
    video_quality: str = "low"  # low, medium, high


@dataclass
class CameraStatus:
    """摄像头状态"""
    connected: bool
    last_frame_time: float
    frame_count: int
    error_message: Optional[str] = None
    resolution: Tuple[int, int] = (0, 0)


class VideoSourceBase(ABC):
    """视频源抽象基类"""

    def __init__(self, config: CameraConfig):
        self.config = config
        self._running = False
        self._status = CameraStatus(
            connected=False,
            last_frame_time=0,
            frame_count=0
        )
        self._frame_queue: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._callbacks: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    @property
    def status(self) -> CameraStatus:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._running

    @abstractmethod
    async def connect(self) -> bool:
        """连接到视频源"""
        pass

    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    async def start_capture(self):
        """开始采集"""
        pass

    @abstractmethod
    async def stop_capture(self):
        """停止采集"""
        pass

    def register_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def unregister_callback(self, event: str, callback: Callable):
        """取消事件回调"""
        if event in self._callbacks:
            self._callbacks[event].remove(callback)

    async def _emit_event(self, event: str, *args, **kwargs):
        """触发事件"""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)


class RTSPVideoSource(VideoSourceBase):
    """
    RTSP视频源实现

    使用 OpenCV 或 ffmpeg-python 连接 RTSP 流
    """

    def __init__(self, config: CameraConfig):
        super().__init__(config)
        self._capture = None
        self._capture_thread: Optional[threading.Thread] = None
        self._reconnect_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """连接到RTSP流"""
        try:
            stream_url = self._build_rtsp_url()
            logger.info(f"Connecting to RTSP stream: {stream_url}")

            if CV2_AVAILABLE:
                self._capture = cv2.VideoCapture(stream_url)
                if not self._capture.isOpened():
                    raise RuntimeError(f"Failed to open RTSP stream: {stream_url}")
            else:
                raise RuntimeError("OpenCV is required for RTSP support")

            self._status.connected = True
            logger.info(f"RTSP stream connected successfully")
            await self._emit_event("connected", self.config.name)
            return True

        except Exception as e:
            logger.error(f"RTSP connection failed: {e}")
            self._status.connected = False
            self._status.error_message = str(e)
            return False

    def _build_rtsp_url(self) -> str:
        """构建RTSP URL"""
        url = self.config.stream_url
        if self.config.username and self.config.password:
            if "@" not in url:
                parsed = url.replace("rtsp://", "")
                url = f"rtsp://{self.config.username}:{self.config.password}@{parsed}"
        return url

    async def disconnect(self):
        """断开连接"""
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=5)

        if self._capture:
            self._capture.release()
            self._capture = None

        self._status.connected = False
        logger.info("RTSP stream disconnected")
        await self._emit_event("disconnected", self.config.name)

    async def start_capture(self):
        """开始采集视频帧"""
        if not self._status.connected:
            success = await self.connect()
            if not success:
                raise RuntimeError("Cannot start capture: not connected")

        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )
        self._capture_thread.start()
        await self._emit_event("capture_started", self.config.name)

    def _capture_loop(self):
        """采集循环 (在独立线程中运行)"""
        while self._running:
            try:
                if self._capture and self._capture.isOpened():
                    ret, frame = self._capture.read()
                    if ret:
                        self._process_frame(frame)
                    else:
                        logger.warning("Failed to read frame, attempting reconnect...")
                        self._handle_disconnect()
                        break
                else:
                    break
            except Exception as e:
                logger.error(f"Capture loop error: {e}")
                break

    def _process_frame(self, frame: np.ndarray):
        """处理视频帧"""
        try:
            timestamp = int(time.time() * 1000)
            self._status.last_frame_time = time.time()
            self._status.frame_count += 1

            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                video_frame = VideoFrame(
                    data=jpeg.tobytes(),
                    timestamp=timestamp,
                    sequence=self._status.frame_count,
                    width=frame.shape[1],
                    height=frame.shape[0],
                    codec=VideoCodec.H264,
                    is_keyframe=True
                )
                self._status.resolution = (frame.shape[1], frame.shape[0])

                try:
                    self._frame_queue.put_nowait(video_frame)
                except queue.Full:
                    pass

                asyncio.create_task(
                    self._emit_event("frame", self.config.name, video_frame)
                )
        except Exception as e:
            logger.error(f"Frame processing error: {e}")

    async def stop_capture(self):
        """停止采集"""
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=5)
        await self._emit_event("capture_stopped", self.config.name)

    async def _handle_disconnect(self):
        """处理断开连接"""
        self._status.connected = False
        await self._emit_event("disconnected", self.config.name)

        if self.config.auto_reconnect:
            await self._schedule_reconnect()

    async def _schedule_reconnect(self):
        """调度重连"""
        retries = 0
        while retries < self.config.max_retries and self._running:
            logger.info(f"Reconnecting in {self.config.retry_interval}s... (attempt {retries + 1})")
            await asyncio.sleep(self.config.retry_interval)

            success = await self.connect()
            if success:
                await self.start_capture()
                return

            retries += 1

        logger.error("Max reconnection attempts reached")


class ONVIFVideoSource(VideoSourceBase):
    """
    ONVIF视频源实现

    支持ONVIF协议的网络摄像头
    """

    def __init__(self, config: CameraConfig):
        super().__init__(config)
        self._onvif_service = None
        self._media_service = None
        self._ptz_service = None

    async def connect(self) -> bool:
        """连接到ONVIF设备"""
        try:
            from onvif import ONVIFCamera

            url_parts = self._parse_url(self.config.stream_url)

            self._onvif_service = ONVIFCamera(
                url_parts["host"],
                url_parts["port"],
                self.config.username,
                self.config.password,
                wsdl_dir=None
            )

            self._media_service = self._onvif_service.create_media_service()
            self._ptz_service = self._onvif_service.create_ptz_service()

            profiles = self._media_service.GetProfiles()
            if not profiles:
                raise RuntimeError("No profiles found on ONVIF device")

            self._status.connected = True
            logger.info(f"ONVIF device connected: {self.config.name}")
            await self._emit_event("connected", self.config.name)
            return True

        except ImportError:
            logger.error("ONVIF library not installed. Run: pip install onvif-py")
            return False
        except Exception as e:
            logger.error(f"ONVIF connection failed: {e}")
            self._status.error_message = str(e)
            return False

    def _parse_url(self, url: str) -> Dict[str, Any]:
        """解析ONVIF设备URL"""
        url = url.replace("onvif://", "http://")
        if "://" not in url:
            url = f"http://{url}"

        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        return {
            "host": parsed.hostname or url.split("/")[0],
            "port": parsed.port or 80,
            "path": parsed.path
        }

    async def disconnect(self):
        """断开ONVIF连接"""
        self._running = False
        self._status.connected = False
        await self._emit_event("disconnected", self.config.name)

    async def start_capture(self):
        """开始ONVIF流采集"""
        if not self._status.connected:
            success = await self.connect()
            if not success:
                raise RuntimeError("Cannot start capture: ONVIF not connected")

        self._running = True
        asyncio.create_task(self._onvif_capture_loop())

    async def _onvif_capture_loop(self):
        """ONVIF采集循环"""
        while self._running:
            try:
                snapshot = self._media_service.GetSnapshotUri(
                    self._media_service.GetProfiles()[0].token
                )
                # Download and process snapshot
                # Note: ONVIF snapshot is not real-time, consider using RTSP for streaming
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"ONVIF capture error: {e}")
                break

    async def stop_capture(self):
        """停止采集"""
        self._running = False

    async def ptz_move(self, pan: float, tilt: float, zoom: float):
        """PTZ移动控制"""
        if self._ptz_service:
            # PTZ movement implementation
            pass


class VideoStreamManager:
    """
    视频流管理器

    统一管理多个视频源，提供集中式访问接口
    """

    def __init__(self):
        self._sources: Dict[str, VideoSourceBase] = {}
        self._lock = asyncio.Lock()

    async def add_source(self, config: CameraConfig) -> str:
        """添加视频源"""
        async with self._lock:
            source_id = str(uuid.uuid4())

            if config.protocol == VideoProtocol.RTSP:
                source = RTSPVideoSource(config)
            elif config.protocol == VideoProtocol.ONVIF:
                source = ONVIFVideoSource(config)
            else:
                raise ValueError(f"Unsupported protocol: {config.protocol}")

            self._sources[source_id] = source
            logger.info(f"Video source added: {source_id} ({config.name})")
            return source_id

    async def remove_source(self, source_id: str):
        """移除视频源"""
        async with self._lock:
            if source_id in self._sources:
                source = self._sources[source_id]
                await source.disconnect()
                del self._sources[source_id]
                logger.info(f"Video source removed: {source_id}")

    async def connect(self, source_id: str) -> bool:
        """连接指定视频源"""
        if source_id not in self._sources:
            raise KeyError(f"Source not found: {source_id}")
        return await self._sources[source_id].connect()

    async def start_capture(self, source_id: str):
        """开始采集指定视频源"""
        if source_id not in self._sources:
            raise KeyError(f"Source not found: {source_id}")
        await self._sources[source_id].start_capture()

    async def get_frame(self, source_id: str, timeout: float = 5.0) -> Optional[VideoFrame]:
        """获取视频帧"""
        if source_id not in self._sources:
            raise KeyError(f"Source not found: {source_id}")

        source = self._sources[source_id]
        try:
            return await asyncio.wait_for(source._frame_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def get_status(self, source_id: str) -> CameraStatus:
        """获取视频源状态"""
        if source_id not in self._sources:
            raise KeyError(f"Source not found: {source_id}")
        return self._sources[source_id].status

    def list_sources(self) -> List[Dict[str, Any]]:
        """列出所有视频源"""
        return [
            {
                "id": source_id,
                "name": source.config.name,
                "protocol": source.config.protocol.value,
                "status": source.status,
                "running": source.is_running
            }
            for source_id, source in self._sources.items()
        ]

    async def register_frame_callback(
        self,
        source_id: str,
        callback: Callable[[str, VideoFrame], Coroutine]
    ):
        """为指定源注册帧回调"""
        if source_id not in self._sources:
            raise KeyError(f"Source not found: {source_id}")
        self._sources[source_id].register_callback("frame", callback)

    async def connect_all(self):
        """连接所有视频源"""
        for source_id, source in self._sources.items():
            try:
                await source.connect()
            except Exception as e:
                logger.error(f"Failed to connect {source_id}: {e}")

    async def disconnect_all(self):
        """断开所有视频源"""
        for source_id, source in self._sources.items():
            try:
                await source.disconnect()
            except Exception as e:
                logger.error(f"Failed to disconnect {source_id}: {e}")


class VideoFrameCache:
    """
    视频帧缓存

    用于存储最近帧，支持运动检测等功能
    """

    def __init__(self, max_frames: int = 30):
        self._frames: List[VideoFrame] = []
        self._max_frames = max_frames
        self._lock = asyncio.Lock()

    async def add_frame(self, frame: VideoFrame):
        """添加帧"""
        async with self._lock:
            self._frames.append(frame)
            if len(self._frames) > self._max_frames:
                self._frames.pop(0)

    async def get_recent_frames(self, count: int = 10) -> List[VideoFrame]:
        """获取最近的N帧"""
        async with self._lock:
            return self._frames[-count:]

    async def get_latest_frame(self) -> Optional[VideoFrame]:
        """获取最新帧"""
        async with self._lock:
            return self._frames[-1] if self._frames else None


async def example_usage():
    """使用示例"""
    manager = VideoStreamManager()

    rtsp_config = CameraConfig(
        name="Front Door Camera",
        stream_url="rtsp://192.168.1.100:554/stream1",
        protocol=VideoProtocol.RTSP,
        username="admin",
        password="password",
        auto_reconnect=True
    )

    source_id = await manager.add_source(rtsp_config)

    async def on_frame(source_id: str, frame: VideoFrame):
        print(f"Received frame from {source_id}: {frame.width}x{frame.height}")

    await manager.register_frame_callback(source_id, on_frame)
    await manager.connect(source_id)
    await manager.start_capture(source_id)

    await asyncio.sleep(60)

    await manager.disconnect_all()


if __name__ == "__main__":
    asyncio.run(example_usage())
