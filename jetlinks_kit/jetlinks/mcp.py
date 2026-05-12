# -*- coding: utf-8 -*-
"""
JetLinks MCP Server.
"""
import logging
from typing import Annotated, Any, Dict, List
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from .types import (
    JetLinksDeviceInfo,
    JetLinksSceneInfo,
    JetLinksSetPropertyParam,
    JetLinksGetPropertyParam
)

_LOGGER = logging.getLogger(__name__)


class McpJetLinksDeviceInfo(BaseModel):
    """JetLinks 设备信息 MCP 模型"""
    id: str = Field(description="设备 ID")
    name: str = Field(description="设备名称")
    online: bool = Field(description="设备在线状态")
    product_name: str = Field(description="产品名称")
    location: str = Field(description="位置")


class McpJetLinksSceneInfo(BaseModel):
    """JetLinks 场景信息 MCP 模型"""
    id: str = Field(description="场景 ID")
    name: str = Field(description="场景名称")
    enabled: bool = Field(description="是否启用")
    description: str = Field(description="描述")


class JetLinksMcpInterface(BaseModel):
    """JetLinks MCP 接口定义"""
    get_devices_async: Any  # 应为 Callable[[], Coroutine[Any, Any, Dict[str, JetLinksDeviceInfo]]]
    set_property_async: Any  # 应为 Callable[[JetLinksSetPropertyParam], Coroutine[Any, Any, bool]]
    get_property_async: Any  # 应为 Callable[[JetLinksGetPropertyParam], Coroutine[Any, Any, Any]]
    get_scenes_async: Any  # 应为 Callable[[], Coroutine[Any, Any, Dict[str, JetLinksSceneInfo]]]
    trigger_scene_async: Any  # 应为 Callable[[str], Coroutine[Any, Any, bool]]


class JetLinksMcp:
    """JetLinks MCP 服务器"""
    
    def __init__(
        self,
        interface: JetLinksMcpInterface,
        name: str = "JetLinks IoT",
        instructions: str = "支持查询和控制 JetLinks 物联网平台的设备和场景"
    ) -> None:
        """
        初始化 JetLinks MCP 服务器
        
        Args:
            interface: JetLinks 接口实现
            name: MCP 服务器名称
            instructions: MCP 服务器说明
        """
        self._interface = interface
        self._name = name
        self._instructions = instructions
        self._mcp: FastMCP | None = None
        self._devices: Dict[str, JetLinksDeviceInfo] = {}
        self._scenes: Dict[str, JetLinksSceneInfo] = {}
        self._initialized = False

    async def init_async(self) -> None:
        """异步初始化 MCP 服务器"""
        if self._initialized:
            return

        self._mcp = FastMCP(
            name=self._name,
            instructions=self._instructions,
            on_duplicate_tools="replace"
        )
        
        # 注册工具
        self._register_tools()
        
        # 初始化时获取设备和场景列表
        try:
            self._devices = await self._interface.get_devices_async()
            self._scenes = await self._interface.get_scenes_async()
        except Exception as e:
            _LOGGER.warning("初始化时获取设备或场景失败: %s", str(e))
        
        self._initialized = True
        _LOGGER.info("JetLinks MCP 服务器初始化成功")

    @property
    def mcp_instance(self) -> FastMCP:
        """获取 MCP 实例"""
        if not self._mcp:
            raise RuntimeError("MCP 服务器未初始化，请先调用 init_async()")
        return self._mcp

    def _register_tools(self) -> None:
        """注册 MCP 工具"""
        if not self._mcp:
            return

        # 获取设备列表工具
        @self._mcp.tool()
        async def get_devices(
            location: Annotated[str | None, "按位置过滤设备（可选）"] = None
        ) -> List[McpJetLinksDeviceInfo]:
            """
            获取 JetLinks 平台设备列表
            
            Args:
                location: 按位置过滤（可选）
            
            Returns:
                设备信息列表
            """
            self._devices = await self._interface.get_devices_async()
            
            devices = list(self._devices.values())
            
            if location:
                devices = [d for d in devices if d.location and location in d.location]
            
            return [
                McpJetLinksDeviceInfo(
                    id=d.id,
                    name=d.name,
                    online=d.online,
                    product_name=d.product_name or "",
                    location=d.location or ""
                )
                for d in devices
            ]

        # 获取场景列表工具
        @self._mcp.tool()
        async def get_scenes() -> List[McpJetLinksSceneInfo]:
            """
            获取 JetLinks 平台场景列表
            
            Returns:
                场景信息列表
            """
            self._scenes = await self._interface.get_scenes_async()
            
            return [
                McpJetLinksSceneInfo(
                    id=s.id,
                    name=s.name,
                    enabled=s.enabled,
                    description=s.description or ""
                )
                for s in self._scenes.values()
            ]

        # 触发场景工具
        @self._mcp.tool()
        async def trigger_scene(
            scene_id: Annotated[str, "场景 ID，通过 get_scenes 获取"]
        ) -> bool:
            """
            触发 JetLinks 场景
            
            Args:
                scene_id: 场景 ID
            
            Returns:
                是否成功
            """
            if scene_id not in self._scenes:
                # 重新获取场景列表
                self._scenes = await self._interface.get_scenes_async()
                if scene_id not in self._scenes:
                    raise ValueError(f"场景不存在: {scene_id}")
            
            return await self._interface.trigger_scene_async(scene_id)

        # 设置设备属性工具
        @self._mcp.tool()
        async def set_device_property(
            device_id: Annotated[str, "设备 ID，通过 get_devices 获取"],
            property_id: Annotated[str, "属性 ID"],
            value: Annotated[Any, "属性值"]
        ) -> bool:
            """
            设置设备属性
            
            Args:
                device_id: 设备 ID
                property_id: 属性 ID
                value: 属性值
            
            Returns:
                是否成功
            """
            if device_id not in self._devices:
                # 重新获取设备列表
                self._devices = await self._interface.get_devices_async()
                if device_id not in self._devices:
                    raise ValueError(f"设备不存在: {device_id}")
            
            param = JetLinksSetPropertyParam(
                device_id=device_id,
                property_id=property_id,
                value=value
            )
            
            return await self._interface.set_property_async(param)

        # 获取设备属性工具
        @self._mcp.tool()
        async def get_device_property(
            device_id: Annotated[str, "设备 ID，通过 get_devices 获取"],
            property_id: Annotated[str, "属性 ID"]
        ) -> Any:
            """
            获取设备属性值
            
            Args:
                device_id: 设备 ID
                property_id: 属性 ID
            
            Returns:
                属性值
            """
            if device_id not in self._devices:
                # 重新获取设备列表
                self._devices = await self._interface.get_devices_async()
                if device_id not in self._devices:
                    raise ValueError(f"设备不存在: {device_id}")
            
            param = JetLinksGetPropertyParam(
                device_id=device_id,
                property_id=property_id
            )
            
            return await self._interface.get_property_async(param)
