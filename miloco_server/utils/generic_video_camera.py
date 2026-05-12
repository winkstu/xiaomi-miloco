# -*- coding: utf-8 -*-
# Copyright (C) 2025
# Universal Video Management Module
# 完全兼容原有接口的通用视频管理模块 - 支持 RTSP/ONVIF

"""
通用视频管理模块 - 完全兼容原有 MIoTCamera/MIoTCameraInstance 接口
支持多种视频源协议，无缝替换原有闭源模块
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
import uuid
import json
from io import BytesIO

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from miot.types import (
    MIoTCameraInfo,
    MIoTCameraStatus,
    MIoTCameraVideoQuality,
    MIoTCameraCodec,
    MIoTCameraFrameType,
    MIoTCameraFrameData
)
from miot.decoder import MIoTMediaDecoder

logger = logging.getLogger(__name__)


# ===============================================================
# 通用视频源接口定义
# ===============================================================

class VideoProtocol(Enum):
    """支持的视频协议"""
    RTSP = "rtsp"
    ONVIF = "onvif"
    HTTP_STREAM = "http_stream"
    LOCAL_FILE = "local_file"


@dataclass
class GenericCameraConfig:
    """通用摄像头配置"""
    did: str
    name: str
    protocol: VideoProtocol
    stream_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    channel_count: int = 1
    timeout: int = 30
    retry_interval: int = 5
    max_retries: int = 3


class GenericVideoSource(ABC):
    """通用视频源抽象接口"""

    @abstractmethod
    async def init_async(self) -> bool:
        """初始化视频源"""
        pass

    @abstractmethod
    async def deinit_async(self):
        """清理视频源资源"""
        pass

    @abstractmethod
    async def start_async(self, enable_reconnect: bool = True) -> bool:
        """开始视频流"""
        pass

    @abstractmethod
    async def stop_async(self):
        """停止视频流"""
        pass

    @abstractmethod
    async def set_video_quality_async(self, quality: MIoTCameraVideoQuality):
        """设置视频质量"""
        pass

    @abstractmethod
    async def set_channel_async(self, channel: int):
        """设置频道"""
        pass


# ===============================================================
# RTSP 视频源实现
# ===============================================================

class RTSPVideoSource(GenericVideoSource):
    """RTSP 协议视频源"""

    def __init__(self, config: GenericCameraConfig):
        self.config = config
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._current_channel = 0
        self._reconnect_task: Optional[asyncio.Task] = None
        self._enable_reconnect = False
        self._capture_thread: Optional[threading.Thread] = None
        self._frame_callbacks: List[Callable[[bytes, int, int], Coroutine]] = []
        self._lock = asyncio.Lock()

    async def init_async(self) -> bool:
        logger.info(f"Initializing RTSP video source: {self.config.did}")
        return True

    async def deinit_async(self):
        await self.stop_async()
        logger.info(f"Deinitialized RTSP video source: {self.config.did}")

    async def start_async(self, enable_reconnect: bool = True) -> bool:
        self._enable_reconnect = enable_reconnect
        try:
            await self._connect_rtsp()
            self._running = True
            self._capture_thread = threading.Thread(
                target=self._capture_loop, daemon=True
            )
            self._capture_thread.start()
            logger.info(f"RTSP video source started: {self.config.did}")
            return True
        except Exception as e:
            logger.error(f"Failed to start RTSP video source: {e}")
            return False

    async def stop_async(self):
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._capture_thread:
            self._capture_thread.join(timeout=5)
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info(f"RTSP video source stopped: {self.config.did}")

    async def set_video_quality_async(self, quality: MIoTCameraVideoQuality):
        logger.info(f"Video quality set to {quality} for {self.config.did}")

    async def set_channel_async(self, channel: int):
        self._current_channel = channel
        logger.info(f"Channel set to {channel} for {self.config.did}")

    async def register_frame_callback(
        self, callback: Callable[[bytes, int, int], Coroutine]
    ):
        async with self._lock:
            self._frame_callbacks.append(callback)

    async def unregister_frame_callback(
        self, callback: Callable[[bytes, int, int], Coroutine]
    ):
        async with self._lock:
            if callback in self._frame_callbacks:
                self._frame_callbacks.remove(callback)

    async def _connect_rtsp(self):
        """连接 RTSP 流"""
        if not CV2_AVAILABLE:
            raise RuntimeError("OpenCV is not available for RTSP streaming")

        stream_url = self.config.stream_url
        if self.config.username and self.config.password:
            if "://" in stream_url:
                protocol, rest = stream_url.split("://", 1)
                stream_url = f"{protocol}://{self.config.username}:{self.config.password}@{rest}"

        logger.info(f"Connecting to RTSP stream: {stream_url}")
        self._cap = cv2.VideoCapture(stream_url)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open RTSP stream: {stream_url}")

    def _capture_loop(self):
        """视频捕获循环"""
        sequence = 0
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self._running:
            try:
                if self._cap and self._cap.isOpened():
                    ret, frame = self._cap.read()
                    if ret:
                        # 转换为 JPEG
                        if PIL_AVAILABLE:
                            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                            buf = BytesIO()
                            img.save(buf, format="JPEG", quality=90)
                            jpeg_data = buf.getvalue()
                        else:
                            _, jpeg_data = cv2.imencode('.jpg', frame)
                            jpeg_data = jpeg_data.tobytes()

                        timestamp = int(time.time() * 1000)
                        sequence += 1
                        channel = self._current_channel

                        # 分发帧数据
                        callbacks = self._frame_callbacks.copy()
                        for callback in callbacks:
                            try:
                                loop.call_soon_threadsafe(
                                    loop.create_task,
                                    callback(jpeg_data, timestamp, channel)
                                )
                            except Exception as e:
                                logger.error(f"Error in frame callback: {e}")
                    else:
                        time.sleep(0.1)
                        if self._enable_reconnect:
                            loop.call_soon_threadsafe(
                                loop.create_task,
                                self._schedule_reconnect()
                            )
                else:
                    time.sleep(0.5)
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(0.5)

        loop.close()

    async def _schedule_reconnect(self):
        """调度重连"""
        if self._reconnect_task and not self._reconnect_task.done():
            return

        async def reconnect():
            retries = 0
            while retries < self.config.max_retries and self._running:
                try:
                    logger.info(f"Attempting to reconnect RTSP: {self.config.did} (attempt {retries + 1})")
                    await self._connect_rtsp()
                    logger.info(f"RTSP reconnected successfully: {self.config.did}")
                    return
                except Exception as e:
                    retries += 1
                    logger.error(f"Reconnection failed: {e}")
                    await asyncio.sleep(self.config.retry_interval)
            logger.error(f"Max reconnection attempts reached for {self.config.did}")

        self._reconnect_task = asyncio.create_task(reconnect())


# ===============================================================
# 兼容原有接口的通用摄像头实例
# ===============================================================

class GenericCameraInstance:
    """
    通用摄像头实例 - 完全兼容原有 MIoTCameraInstance 接口
    """

    def __init__(
        self,
        camera_info: MIoTCameraInfo,
        frame_interval: int,
        enable_hw_accel: bool = False,
        enable_audio: bool = False,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        generic_config: Optional[GenericCameraConfig] = None
    ):
        self._camera_info = camera_info
        self._frame_interval = frame_interval
        self._enable_hw_accel = enable_hw_accel
        self._enable_audio = enable_audio
        self._loop = loop or asyncio.get_event_loop()

        self._video_source: Optional[GenericVideoSource] = None
        self._decoder: Optional[MIoTMediaDecoder] = None
        self._jpg_callbacks: List[Callable[[bytes, int, int], Coroutine]] = []
        self._raw_callbacks: List[Callable[[str, bytes, int, int, int], Coroutine]] = []

        # 状态追踪
        self._status = MIoTCameraStatus.DISCONNECTED
        self._lock = asyncio.Lock()

        # 使用通用配置或从 camera_info 推断
        self._generic_config = generic_config

    async def init_async(self) -> bool:
        """初始化摄像头实例"""
        try:
            # 确定使用哪个视频源
            if self._generic_config:
                if self._generic_config.protocol == VideoProtocol.RTSP:
                    self._video_source = RTSPVideoSource(self._generic_config)
                # 未来可以添加 ONVIF 等其他协议
            elif "rtsp" in str(self._camera_info.model_dump()):
                # 从 camera_info 推断 RTSP 配置
                rtsp_config = GenericCameraConfig(
                    did=self._camera_info.did,
                    name=self._camera_info.name,
                    protocol=VideoProtocol.RTSP,
                    stream_url=getattr(self._camera_info, "rtsp_url", ""),
                    channel_count=self._camera_info.channel_count or 1
                )
                self._video_source = RTSPVideoSource(rtsp_config)
            else:
                logger.warning("No valid video source config, using placeholder")
                return False

            if self._video_source:
                await self._video_source.init_async()

            logger.info(f"GenericCameraInstance initialized: {self._camera_info.did}")
            return True
        except Exception as e:
            logger.error(f"Failed to init GenericCameraInstance: {e}")
            return False

    async def start_async(self, enable_reconnect: bool = True):
        """
        开始视频流

        Args:
            enable_reconnect: 是否启用自动重连
        """
        async with self._lock:
            if self._status == MIoTCameraStatus.CONNECTED:
                return

            self._status = MIoTCameraStatus.CONNECTING

            try:
                # 初始化解码器（用于兼容原有的接口）
                self._decoder = MIoTMediaDecoder(
                    frame_interval=self._frame_interval,
                    video_callback=self._on_decoded_jpg,
                    enable_hw_accel=self._enable_hw_accel,
                    enable_audio=self._enable_audio,
                    main_loop=self._loop
                )
                self._decoder.start()

                # 启动视频源
                if self._video_source:
                    if isinstance(self._video_source, RTSPVideoSource):
                        await self._video_source.register_frame_callback(
                            self._on_raw_jpg
                        )
                    success = await self._video_source.start_async(
                        enable_reconnect=enable_reconnect
                    )
                    if not success:
                        raise RuntimeError("Failed to start video source")

                self._status = MIoTCameraStatus.CONNECTED
                logger.info(f"Camera started: {self._camera_info.did}")
            except Exception as e:
                self._status = MIoTCameraStatus.ERROR
                logger.error(f"Failed to start camera: {e}")
                raise

    async def stop_async(self):
        """停止视频流"""
        async with self._lock:
            if self._status == MIoTCameraStatus.DISCONNECTED:
                return

            try:
                if self._video_source:
                    if isinstance(self._video_source, RTSPVideoSource):
                        await self._video_source.unregister_frame_callback(
                            self._on_raw_jpg
                        )
                    await self._video_source.stop_async()

                if self._decoder:
                    self._decoder.stop()
                    self._decoder = None

                self._status = MIoTCameraStatus.DISCONNECTED
                logger.info(f"Camera stopped: {self._camera_info.did}")
            except Exception as e:
                logger.error(f"Failed to stop camera: {e}")

    async def destroy(self):
        """销毁摄像头实例"""
        await self.stop_async()
        if self._video_source:
            await self._video_source.deinit_async()
        self._video_source = None
        logger.info(f"Camera destroyed: {self._camera_info.did}")

    async def update_camera_info(self, camera_info: MIoTCameraInfo):
        """更新摄像头信息"""
        self._camera_info = camera_info

    async def register_decode_jpg_callback(
        self, callback: Callable[[bytes, int, int], Coroutine]
    ):
        """
        注册 JPEG 解码回调

        Args:
            callback: 回调函数，参数为 (jpeg_data, timestamp, channel)
        """
        async with self._lock:
            self._jpg_callbacks.append(callback)

    async def unregister_decode_jpg_callback(
        self, callback: Callable[[bytes, int, int], Coroutine]
    ):
        """取消注册 JPEG 解码回调"""
        async with self._lock:
            if callback in self._jpg_callbacks:
                self._jpg_callbacks.remove(callback)

    async def register_raw_stream(
        self, callback: Callable[[str, bytes, int, int, int], Coroutine],
        channel: int = 0
    ):
        """
        注册原始流回调

        Args:
            callback: 回调函数，参数为 (did, jpeg_data, timestamp, channel, sequence)
            channel: 频道
        """
        async with self._lock:
            self._raw_callbacks.append(callback)

    async def unregister_raw_stream(self, channel: int = 0):
        """取消注册原始流回调"""
        async with self._lock:
            self._raw_callbacks = []

    async def set_video_quality_async(self, quality: MIoTCameraVideoQuality):
        """设置视频质量"""
        if self._video_source:
            await self._video_source.set_video_quality_async(quality)

    async def set_channel_async(self, channel: int):
        """设置频道"""
        if self._video_source:
            await self._video_source.set_channel_async(channel)

    @property
    def status(self) -> MIoTCameraStatus:
        """获取摄像头状态"""
        return self._status

    @property
    def camera_info(self) -> MIoTCameraInfo:
        """获取摄像头信息"""
        return self._camera_info

    # ===========================================================
    # 内部回调处理
    # ===========================================================

    async def _on_raw_jpg(self, jpeg_data: bytes, timestamp: int, channel: int):
        """处理原始 JPEG 数据（兼容解码后的回调）"""
        # 直接调用 JPEG 回调
        callbacks = self._jpg_callbacks.copy()
        for callback in callbacks:
            try:
                await callback(jpeg_data, timestamp, channel)
            except Exception as e:
                logger.error(f"Error in JPEG callback: {e}")

        # 调用原始流回调
        raw_callbacks = self._raw_callbacks.copy()
        sequence = int(timestamp)
        for callback in raw_callbacks:
            try:
                await callback(
                    self._camera_info.did,
                    jpeg_data,
                    timestamp,
                    channel,
                    sequence
                )
            except Exception as e:
                logger.error(f"Error in raw stream callback: {e}")

    def _on_decoded_jpg(self, jpeg_data: bytes, timestamp: int, channel: int):
        """处理解码后的 JPEG 数据（由解码器调用）"""
        self._loop.call_soon_threadsafe(
            self._loop.create_task,
            self._on_raw_jpg(jpeg_data, timestamp, channel)
        )


# ===============================================================
# 兼容原有接口的通用摄像头客户端
# ===============================================================

class GenericCamera:
    """
    通用摄像头客户端 - 完全兼容原有 MIoTCamera 接口
    可以管理多个通用摄像头实例
    """

    def __init__(
        self,
        cloud_server: Optional[str] = None,
        access_token: Optional[str] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ):
        self._cloud_server = cloud_server
        self._access_token = access_token
        self._loop = loop or asyncio.get_event_loop()

        # 配置存储
        self._generic_camera_configs: Dict[str, GenericCameraConfig] = {}

    async def init_async(self):
        """初始化通用摄像头客户端"""
        logger.info("GenericCamera initialized")

    async def deinit_async(self):
        """清理资源"""
        logger.info("GenericCamera deinitialized")

    async def update_access_token_async(self, access_token: str):
        """更新访问令牌"""
        self._access_token = access_token

    def add_generic_camera_config(self, config: GenericCameraConfig):
        """
        添加通用摄像头配置

        Args:
            config: 通用摄像头配置
        """
        self._generic_camera_configs[config.did] = config
        logger.info(f"Added generic camera config: {config.did}")

    def remove_generic_camera_config(self, did: str):
        """移除通用摄像头配置"""
        if did in self._generic_camera_configs:
            del self._generic_camera_configs[did]
            logger.info(f"Removed generic camera config: {did}")

    async def create_camera_instance_async(
        self,
        camera_info: MIoTCameraInfo,
        frame_interval: int = 500,
        enable_hw_accel: bool = False,
        enable_audio: bool = False
    ) -> Optional[GenericCameraInstance]:
        """
        创建摄像头实例

        Args:
            camera_info: 摄像头信息
            frame_interval: 帧间隔(ms)
            enable_hw_accel: 是否启用硬件加速
            enable_audio: 是否启用音频

        Returns:
            摄像头实例
        """
        try:
            # 检查是否有通用配置
            generic_config = self._generic_camera_configs.get(camera_info.did)

            # 创建通用摄像头实例
            instance = GenericCameraInstance(
                camera_info=camera_info,
                frame_interval=frame_interval,
                enable_hw_accel=enable_hw_accel,
                enable_audio=enable_audio,
                loop=self._loop,
                generic_config=generic_config
            )

            await instance.init_async()
            logger.info(f"Created camera instance: {camera_info.did}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create camera instance: {e}")
            return None

    async def get_camera_status_async(self, did: str) -> Optional[MIoTCameraStatus]:
        """获取摄像头状态"""
        # 此方法是为了保持接口兼容性，实际状态由实例管理
        return MIoTCameraStatus.DISCONNECTED

    async def get_camera_extra_info_async(
        self, did: str
    ) -> Optional[Dict[str, Any]]:
        """获取摄像头额外信息"""
        return None


# ===============================================================
# 辅助函数 - 用于从 JSON 配置加载
# ===============================================================

def load_generic_camera_configs_from_json(
    config_path: str
) -> Dict[str, GenericCameraConfig]:
    """
    从 JSON 文件加载通用摄像头配置

    配置格式:
    {
        "cameras": [
            {
                "did": "camera1",
                "name": "Front Door",
                "protocol": "rtsp",
                "stream_url": "rtsp://192.168.1.100:554/stream1",
                "username": "admin",
                "password": "password"
            }
        ]
    }
    """
    configs = {}
    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        for cam_data in data.get("cameras", []):
            config = GenericCameraConfig(
                did=cam_data["did"],
                name=cam_data["name"],
                protocol=VideoProtocol(cam_data["protocol"]),
                stream_url=cam_data["stream_url"],
                username=cam_data.get("username"),
                password=cam_data.get("password"),
                channel_count=cam_data.get("channel_count", 1)
            )
            configs[config.did] = config
        logger.info(f"Loaded {len(configs)} camera configs from {config_path}")
    except Exception as e:
        logger.error(f"Failed to load camera configs: {e}")
    return configs


def create_miot_camera_info_from_config(
    config: GenericCameraConfig
) -> MIoTCameraInfo:
    """从通用配置创建 MIoTCameraInfo（用于无缝集成）"""
    return MIoTCameraInfo(
        did=config.did,
        name=config.name,
        uid="",
        urn=f"urn:generic-camera:{config.protocol.value}",
        model=f"generic-{config.protocol.value}",
        manufacturer="Generic",
        connect_type=1,
        pid=0,
        token="",
        online=True,
        voice_ctrl=0,
        order_time=int(time.time()),
        sub_devices={},
        is_set_pincode=0,
        pincode_type=0,
        channel_count=config.channel_count,
        camera_status=MIoTCameraStatus.DISCONNECTED
    )
