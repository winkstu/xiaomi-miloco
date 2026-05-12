# -*- coding: utf-8 -*-
"""
JetLinks Type Definitions.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JetLinksDeviceInfo(BaseModel):
    """JetLinks Device Info."""
    id: str = Field(description="Device ID")
    name: str = Field(description="Device name")
    product_id: str = Field(description="Product ID")
    product_name: Optional[str] = Field(default=None, description="Product name")
    state: str = Field(description="Device state (online/offline)")
    create_time: Optional[int] = Field(default=None, description="Create time")
    modify_time: Optional[int] = Field(default=None, description="Modify time")
    manufacturer: Optional[str] = Field(default=None, description="Manufacturer")
    model: Optional[str] = Field(default=None, description="Model")
    location: Optional[str] = Field(default=None, description="Location")
    description: Optional[str] = Field(default=None, description="Description")
    
    @property
    def online(self) -> bool:
        return self.state.lower() == "online"


class JetLinksPropertyInfo(BaseModel):
    """JetLinks Property Info."""
    id: str = Field(description="Property ID")
    name: str = Field(description="Property name")
    value_type: str = Field(description="Value type")
    description: Optional[str] = Field(default=None, description="Description")
    readable: bool = Field(default=True, description="Readable")
    writable: bool = Field(default=True, description="Writable")


class JetLinksSceneInfo(BaseModel):
    """JetLinks Scene Info."""
    id: str = Field(description="Scene ID")
    name: str = Field(description="Scene name")
    description: Optional[str] = Field(default=None, description="Description")
    state: str = Field(default="enabled", description="Scene state (enabled/disabled)")
    create_time: Optional[int] = Field(default=None, description="Create time")
    
    @property
    def enabled(self) -> bool:
        return self.state.lower() == "enabled"


class JetLinksSetPropertyParam(BaseModel):
    """JetLinks Set Property Params."""
    device_id: str = Field(description="Device ID")
    property_id: str = Field(description="Property ID")
    value: Any = Field(description="Property value")


class JetLinksGetPropertyParam(BaseModel):
    """JetLinks Get Property Params."""
    device_id: str = Field(description="Device ID")
    property_id: str = Field(description="Property ID")


class JetLinksTriggerSceneParam(BaseModel):
    """JetLinks Trigger Scene Params."""
    scene_id: str = Field(description="Scene ID")


class JetLinksDeviceProperty(BaseModel):
    """JetLinks Device Property."""
    device_id: str = Field(description="Device ID")
    property_id: str = Field(description="Property ID")
    value: Any = Field(description="Property value")
    timestamp: int = Field(description="Timestamp")
