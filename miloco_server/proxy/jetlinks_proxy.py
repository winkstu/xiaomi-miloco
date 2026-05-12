# Copyright (C) 2025 Xiaomi Corporation
# This software may be used and distributed according to the terms of the Xiaomi Miloco License Agreement.

"""JetLinks proxy module for handling JetLinks IoT platform related operations."""

import asyncio
import json
import logging
from typing import Optional

from pydantic_core import to_jsonable_python
from jetlinks import JetLinksClient
from jetlinks.types import (
    JetLinksDeviceInfo,
    JetLinksSceneInfo
)

from miloco_server.dao.kv_dao import KVDao, DeviceInfoKeys


logger = logging.getLogger(__name__)


class JetLinksProxy:
    """JetLinks proxy class responsible for handling JetLinks IoT platform operations."""
    
    def __init__(
        self,
        base_url: str,
        access_token: Optional[str],
        kv_dao: KVDao,
    ):
        """
        初始化 JetLinks 代理
        
        Args:
            base_url: JetLinks 平台基础 URL
            access_token: 访问令牌（可选）
            kv_dao: 键值对数据访问对象
        """
        self._kv_dao = kv_dao
        self._base_url = base_url
        self._access_token = access_token
        
        # 初始化数据存储
        self._init_jetlinks_info_dict()
        
        # 创建 JetLinks 客户端
        self._jetlinks_client = JetLinksClient(
            base_url=base_url,
            access_token=access_token
        )
        
        self._initialized = False

    @property
    def jetlinks_client(self) -> JetLinksClient:
        """获取 JetLinks 客户端实例"""
        return self._jetlinks_client

    @classmethod
    async def create_jetlinks_proxy(
        cls,
        base_url: str,
        access_token: Optional[str],
        kv_dao: KVDao,
    ) -> "JetLinksProxy":
        """
        异步创建 JetLinks 代理实例
        
        Args:
            base_url: JetLinks 平台基础 URL
            access_token: 访问令牌（可选）
            kv_dao: 键值对数据访问对象
        
        Returns:
            JetLinksProxy 实例
        """
        instance = cls(base_url, access_token, kv_dao)
        await instance.init_jetlinks_info()
        logger.info("JetLinksProxy 初始化成功")
        return instance

    async def init_jetlinks_info(self) -> None:
        """初始化 JetLinks 信息"""
        await self._jetlinks_client.init_async()
        
        # 如果有访问令牌，尝试刷新信息
        if self._access_token:
            await self.refresh_jetlinks_info()
        
        self._initialized = True

    async def refresh_jetlinks_info(self) -> dict:
        """
        刷新所有 JetLinks 信息
        
        Returns:
            包含各刷新操作结果的字典
        """
        result = {
            "devices": False,
            "scenes": False
        }

        device_info_dict = await self.refresh_devices()
        result["devices"] = device_info_dict is not None

        scene_info_dict = await self.refresh_scenes()
        result["scenes"] = scene_info_dict is not None

        logger.info("JetLinks 信息刷新完成: %s", result)
        return result

    def _init_jetlinks_info_dict(self) -> None:
        """初始化 JetLinks 信息字典（从持久化存储中读取）"""
        # 设备信息
        self._device_info_dict: dict[str, JetLinksDeviceInfo] = {}
        device_info_str = self._kv_dao.get(DeviceInfoKeys.JETLINKS_DEVICE_INFO_KEY)
        if device_info_str:
            try:
                device_data = json.loads(device_info_str)
                self._device_info_dict = {
                    did: JetLinksDeviceInfo(**data)
                    for did, data in device_data.items()
                }
            except Exception as e:
                logger.error("解析 JetLinks 设备信息失败: %s", str(e))
        
        # 场景信息
        self._scene_info_dict: dict[str, JetLinksSceneInfo] = {}
        scene_info_str = self._kv_dao.get(DeviceInfoKeys.JETLINKS_SCENE_INFO_KEY)
        if scene_info_str:
            try:
                scene_data = json.loads(scene_info_str)
                self._scene_info_dict = {
                    scene_id: JetLinksSceneInfo(**data)
                    for scene_id, data in scene_data.items()
                }
            except Exception as e:
                logger.error("解析 JetLinks 场景信息失败: %s", str(e))

    async def get_devices(self) -> dict[str, JetLinksDeviceInfo]:
        """
        获取设备列表
        
        Returns:
            设备信息字典
        """
        if not self._device_info_dict:
            logger.warning("未找到设备信息，正在刷新")
            await self.refresh_devices()
        return self._device_info_dict

    async def get_scenes(self) -> dict[str, JetLinksSceneInfo]:
        """
        获取场景列表
        
        Returns:
            场景信息字典
        """
        if not self._scene_info_dict:
            logger.warning("未找到场景信息，正在刷新")
            await self.refresh_scenes()
        return self._scene_info_dict

    async def refresh_devices(self) -> dict[str, JetLinksDeviceInfo] | None:
        """
        刷新设备列表
        
        Returns:
            设备信息字典，失败返回 None
        """
        try:
            devices = await self._jetlinks_client.get_devices_async()
            self._device_info_dict = devices
            
            # 持久化存储
            self._kv_dao.set(
                DeviceInfoKeys.JETLINKS_DEVICE_INFO_KEY,
                json.dumps(to_jsonable_python(devices))
            )
            logger.info("JetLinks 设备刷新成功，共 %d 个设备", len(devices))
            return devices
        except Exception as e:
            logger.error("刷新 JetLinks 设备失败: %s", str(e), exc_info=True)
            return None

    async def refresh_scenes(self) -> dict[str, JetLinksSceneInfo] | None:
        """
        刷新场景列表
        
        Returns:
            场景信息字典，失败返回 None
        """
        try:
            scenes = await self._jetlinks_client.get_scenes_async()
            self._scene_info_dict = scenes
            
            # 持久化存储
            self._kv_dao.set(
                DeviceInfoKeys.JETLINKS_SCENE_INFO_KEY,
                json.dumps(to_jsonable_python(scenes))
            )
            logger.info("JetLinks 场景刷新成功，共 %d 个场景", len(scenes))
            return scenes
        except Exception as e:
            logger.error("刷新 JetLinks 场景失败: %s", str(e), exc_info=True)
            return None

    async def execute_scene(self, scene_id: str) -> bool:
        """
        执行场景
        
        Args:
            scene_id: 场景 ID
        
        Returns:
            是否成功
        """
        try:
            if scene_id not in self._scene_info_dict:
                logger.warning("场景不存在: %s", scene_id)
                return False
            
            return await self._jetlinks_client.trigger_scene_async(scene_id)
        except Exception as e:
            logger.error("执行 JetLinks 场景失败: %s", str(e))
            return False

    def update_access_token(self, access_token: str) -> None:
        """
        更新访问令牌
        
        Args:
            access_token: 新的访问令牌
        """
        self._access_token = access_token
        self._jetlinks_client.set_access_token(access_token)
        logger.info("JetLinks 访问令牌已更新")
