#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 通用视频管理模块 - 快速开始示例

"""
快速开始示例 - 演示如何使用通用视频管理模块
"""

import asyncio
import logging
import time
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入通用视频管理模块
from miloco_server.utils.generic_video_camera import (
    GenericCamera,
    GenericCameraInstance,
    load_generic_camera_configs_from_json,
    create_miot_camera_info_from_config,
    GenericCameraConfig,
    VideoProtocol
)


async def simple_rtsp_camera_example():
    """简单的 RTSP 摄像头示例"""
    logger.info("=== 通用视频管理模块 - RTSP 摄像头示例")

    # 1. 创建摄像头配置
    rtsp_config = GenericCameraConfig(
        did="demo-camera-001",
        name="演示摄像头",
        protocol=VideoProtocol.RTSP,
        stream_url="rtsp://192.168.1.100:554/stream1",
        username="admin",
        password="password",
        channel_count=1
    )

    # 2. 创建通用摄像头客户端
    loop = asyncio.get_event_loop()
    generic_camera = GenericCamera(loop=loop)

    # 3. 初始化
    await generic_camera.init_async()

    # 4. 添加配置
    generic_camera.add_generic_camera_config(rtsp_config)

    # 5. 创建兼容的 MIoTCameraInfo（用于无缝集成）
    camera_info = create_miot_camera_info_from_config(rtsp_config)

    # 6. 创建摄像头实例（与原有接口完全一致）
    logger.info(f"创建摄像头实例: {rtsp_config.did}")
    instance = await generic_camera.create_camera_instance_async(
        camera_info,
        frame_interval=500,
        enable_hw_accel=False
    )

    if not instance:
        logger.error("创建摄像头实例失败！")
        return

    # 7. 定义回调函数（与原有接口完全一致）
    frame_count = 0
    start_time = time.time()

    async def on_jpg_frame(data: bytes, timestamp: int, channel: int):
        nonlocal frame_count
        frame_count += 1
        elapsed = time.time() - start_time
        if frame_count % 10 == 0:
            fps = frame_count / elapsed
            logger.info(f"收到第 {frame_count} 帧 | 帧 (FPS: {fps:.1f})")
            # 保存一帧到文件（可选）
            if frame_count <= 3:
                with open(f"frame_{frame_count}.jpg", "wb") as f:
                    f.write(data)

    # 8. 注册回调
    await instance.register_decode_jpg_callback(on_jpg_frame)

    # 9. 开始视频流
    logger.info("启动视频流...")
    await instance.start_async(enable_reconnect=True)

    # 10. 运行一段时间
    logger.info("视频流运行中... (10秒后停止")
    await asyncio.sleep(10)

    # 11. 停止并清理
    logger.info("停止视频流...")
    await instance.stop_async()
    await instance.destroy()
    await generic_camera.deinit_async()

    logger.info("示例运行完毕！")


async def config_file_example():
    """配置文件示例"""
    logger.info("=== 通用视频管理模块 - 配置文件示例")

    # 检查配置文件是否存在
    config_path = Path("generic_cameras.json")
    if not config_path.exists():
        logger.warning("配置文件 generic_cameras.json 不存在，使用示例配置")
        example_path = Path("generic_cameras_example.json")
        config_path = example_path

    if not config_path.exists():
        logger.warning("没有找到配置文件")
        return

    # 从配置文件加载
    configs = load_generic_camera_configs_from_json(str(config_path))
    logger.info(f"从配置文件加载了 {len(configs)} 个摄像头配置")

    for did, config in configs.items():
        logger.info(f"  - {did}: {config.name} ({config.protocol.value})")


def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║       通用视频管理模块 - 快速开始                           ║
║  Universal Video Management Module - Quick Start                   ║
╚═══════════════════════════════════════════════════════════╝
    """)

    print("\n选择示例:")
    print("1. RTSP 摄像头示例")
    print("2. 配置文件示例")

    choice = input("\n请选择 (1/2): ").strip()

    try:
        if choice == "1":
            asyncio.run(simple_rtsp_camera_example())
        elif choice == "2":
            asyncio.run(config_file_example())
        else:
            print("无效选择")
    except Exception as e:
        logger.error(f"运行示例出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
