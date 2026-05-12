# -*- coding: utf-8 -*-
"""
JetLinks IoT Platform Client.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import aiohttp

from .types import (
    JetLinksDeviceInfo,
    JetLinksSceneInfo,
    JetLinksSetPropertyParam,
    JetLinksGetPropertyParam,
    JetLinksDeviceProperty
)

_LOGGER = logging.getLogger(__name__)


class JetLinksError(Exception):
    """JetLinks 错误基类"""
    pass


class JetLinksClient:
    """JetLinks 物联网平台客户端"""

    def __init__(
        self,
        base_url: str,
        access_token: Optional[str] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> None:
        """
        初始化 JetLinks 客户端

        Args:
            base_url: JetLinks 平台基础 URL，例如 "http://localhost:8848"
            access_token: 访问令牌（可选）
            loop: 事件循环（可选）
        """
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._main_loop = loop or asyncio.get_running_loop()
        self._session: Optional[aiohttp.ClientSession] = None
        self._initialized = False

    async def init_async(self) -> None:
        """异步初始化客户端"""
        if self._initialized:
            return
        
        self._session = aiohttp.ClientSession(loop=self._main_loop)
        self._initialized = True
        _LOGGER.info("JetLinks 客户端初始化成功")

    async def deinit_async(self) -> None:
        """释放资源"""
        if self._session and not self._session.closed:
            await self._session.close()
        self._initialized = False

    def set_access_token(self, access_token: str) -> None:
        """设置访问令牌"""
        self._access_token = access_token

    @property
    def _headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: int = 30
    ) -> Dict:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            path: API 路径
            data: 请求体数据
            params: 查询参数
            timeout: 超时时间（秒）

        Returns:
            响应数据
        """
        if not self._session:
            raise JetLinksError("客户端未初始化，请先调用 init_async()")

        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=self._headers,
                timeout=timeout
            ) as response:
                response_text = await response.text()
                
                if response.status not in [200, 201]:
                    _LOGGER.error(
                        "JetLinks API 请求失败: %s %s, status=%d, response=%s",
                        method, url, response.status, response_text
                    )
                    raise JetLinksError(f"API 请求失败: HTTP {response.status}")

                try:
                    result = json.loads(response_text)
                    return result
                except json.JSONDecodeError:
                    _LOGGER.error("响应解析失败: %s", response_text)
                    raise JetLinksError("响应格式错误")

        except aiohttp.ClientError as e:
            _LOGGER.error("网络请求失败: %s", str(e))
            raise JetLinksError(f"网络请求失败: {str(e)}") from e

    async def get_devices_async(
        self,
        page_size: int = 100,
        page_index: int = 1
    ) -> Dict[str, JetLinksDeviceInfo]:
        """
        获取设备列表

        Args:
            page_size: 每页数量
            page_index: 页码

        Returns:
            设备信息字典，key 为设备 ID
        """
        params = {
            "pageSize": page_size,
            "pageIndex": page_index
        }
        
        result = await self._request(
            method="GET",
            path="/jetlinks/device/instance/_query",
            params=params
        )
        
        devices = {}
        data_list = result.get("data", {}).get("list", [])
        
        for item in data_list:
            device_id = item.get("id", "")
            if device_id:
                devices[device_id] = JetLinksDeviceInfo(
                    id=device_id,
                    name=item.get("name", ""),
                    product_id=item.get("productId", ""),
                    product_name=item.get("productName"),
                    state=item.get("state", "offline"),
                    create_time=item.get("createTime"),
                    modify_time=item.get("modifyTime"),
                    manufacturer=item.get("manufacturer"),
                    model=item.get("model"),
                    location=item.get("location"),
                    description=item.get("description")
                )
        
        return devices

    async def get_device_properties_async(
        self,
        device_id: str
    ) -> Dict[str, JetLinksDeviceProperty]:
        """
        获取设备属性

        Args:
            device_id: 设备 ID

        Returns:
            属性字典，key 为属性 ID
        """
        result = await self._request(
            method="GET",
            path=f"/jetlinks/device/instance/{device_id}/properties/_query"
        )
        
        properties = {}
        data_list = result.get("data", {}).get("list", [])
        
        for item in data_list:
            prop_id = item.get("property", "")
            if prop_id:
                properties[prop_id] = JetLinksDeviceProperty(
                    device_id=device_id,
                    property_id=prop_id,
                    value=item.get("value"),
                    timestamp=item.get("timestamp", 0)
                )
        
        return properties

    async def set_property_async(
        self,
        param: JetLinksSetPropertyParam
    ) -> bool:
        """
        设置设备属性

        Args:
            param: 设置属性参数

        Returns:
            是否成功
        """
        data = {
            "properties": {
                param.property_id: param.value
            }
        }
        
        result = await self._request(
            method="POST",
            path=f"/jetlinks/device/instance/{param.device_id}/property/_set",
            data=data
        )
        
        # 根据 JetLinks API 响应判断是否成功
        return result.get("success", False)

    async def get_property_async(
        self,
        param: JetLinksGetPropertyParam
    ) -> Any:
        """
        获取设备属性值

        Args:
            param: 获取属性参数

        Returns:
            属性值
        """
        properties = await self.get_device_properties_async(param.device_id)
        prop = properties.get(param.property_id)
        return prop.value if prop else None

    async def get_scenes_async(
        self,
        page_size: int = 100,
        page_index: int = 1
    ) -> Dict[str, JetLinksSceneInfo]:
        """
        获取场景列表

        Args:
            page_size: 每页数量
            page_index: 页码

        Returns:
            场景信息字典，key 为场景 ID
        """
        params = {
            "pageSize": page_size,
            "pageIndex": page_index
        }
        
        result = await self._request(
            method="GET",
            path="/jetlinks/scene/_query",
            params=params
        )
        
        scenes = {}
        data_list = result.get("data", {}).get("list", [])
        
        for item in data_list:
            scene_id = item.get("id", "")
            if scene_id:
                scenes[scene_id] = JetLinksSceneInfo(
                    id=scene_id,
                    name=item.get("name", ""),
                    description=item.get("description"),
                    state=item.get("state", "disabled"),
                    create_time=item.get("createTime")
                )
        
        return scenes

    async def trigger_scene_async(self, scene_id: str) -> bool:
        """
        触发场景

        Args:
            scene_id: 场景 ID

        Returns:
            是否成功
        """
        result = await self._request(
            method="POST",
            path=f"/jetlinks/scene/{scene_id}/_trigger"
        )
        
        return result.get("success", False)
