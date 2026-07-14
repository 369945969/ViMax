import asyncio
import aiohttp
import os
import time
from typing import Optional, List, Dict, Any
from interfaces.video_output import VideoOutput


class VideoGeneratorSkyReels:
    """SkyReels-V3 视频生成器"""
    
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "http://jackpyf.cloud:9000",
        timeout: int = 300,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
    async def generate_video(
        self,
        prompt: str,
        duration: int = 5,
        resolution: str = "540P",
        seed: int = 42,
        reference_image_url: Optional[str] = None,
        task_type: str = "img2vid",
        **kwargs,
    ) -> str:
        """
        生成视频
        
        Args:
            prompt: 视频描述提示词
            duration: 视频时长（秒），默认5秒
            resolution: 分辨率，默认540P
            seed: 随机种子
            reference_image_url: 参考图片URL（用于img2vid任务）
            task_type: 任务类型 (img2vid, vid2vid, etc.)
            
        Returns:
            视频文件路径
        """
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        
        # 构建请求数据
        data = aiohttp.FormData()
        data.add_field("task_type", task_type)
        data.add_field("prompt", prompt)
        data.add_field("duration", str(duration))
        data.add_field("resolution", resolution)
        data.add_field("seed", str(seed))
        data.add_field("offload", "true")
        data.add_field("low_vram", "false")
        
        if reference_image_url:
            data.add_field("input_image_url", reference_image_url)
        
        # 提交生成任务
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/v1/generate",
                headers=headers,
                data=data,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 202:
                    error_text = await response.text()
                    raise Exception(f"提交任务失败: {response.status} - {error_text}")
                result = await response.json()
                task_id = result.get("task_id")
                if not task_id:
                    raise Exception(f"未获取到任务ID: {result}")
                print(f"📋 任务已提交: {task_id}")
        
        # 等待任务完成
        video_path = await self._wait_for_task(task_id, headers)
        return video_path
    
    async def _wait_for_task(self, task_id: str, headers: Dict[str, str]) -> str:
        """等待任务完成并下载结果"""
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            while True:
                # 检查超时
                if time.time() - start_time > self.timeout:
                    raise Exception(f"任务超时 ({self.timeout}秒)")
                
                # 获取任务状态
                async with session.get(
                    f"{self.base_url}/api/v1/status/{task_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        await asyncio.sleep(5)
                        continue
                    
                    task_info = await response.json()
                    status = task_info.get("status", "")
                    progress = task_info.get("progress", 0)
                    
                    if status == "completed":
                        # 下载视频
                        download_url = task_info.get("download_url")
                        if download_url:
                            return await self._download_video(session, download_url, task_id, headers)
                        else:
                            raise Exception("任务完成但未找到下载链接")
                    
                    elif status == "failed":
                        error = task_info.get("error", "未知错误")
                        raise Exception(f"任务失败: {error}")
                    
                    else:
                        # 继续等待
                        print(f"⏳ 任务状态: {status}, 进度: {progress*100:.1f}%")
                        await asyncio.sleep(10)
    
    async def _download_video(
        self,
        session: aiohttp.ClientSession,
        download_url: str,
        task_id: str,
        headers: Dict[str, str],
    ) -> str:
        """下载视频文件"""
        # 构建完整URL
        if download_url.startswith("/"):
            download_url = f"{self.base_url}{download_url}"
        
        async with session.get(
            download_url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            if response.status != 200:
                raise Exception(f"下载视频失败: {response.status}")
            
            # 保存视频
            output_dir = ".working_dir/videos"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"skyreels_{task_id}.mp4")
            
            with open(output_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
            
            print(f"✅ 视频已保存: {output_path}")
            return output_path
    
    async def generate_single_video(
        self,
        prompt: str,
        negative_prompt: str = "",
        size: str = "1280x720",
        num_frames: int = 125,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 50,
        fps: int = 24,
        seed: int = -1,
        reference_image_path: Optional[str] = None,
        **kwargs,
    ) -> VideoOutput:
        """
        生成单个视频（兼容 ViMax 协议）
        
        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            size: 视频尺寸
            num_frames: 帧数
            guidance_scale: 引导比例
            num_inference_steps: 推理步数
            fps: 帧率
            seed: 随机种子
            reference_image_path: 参考图片路径
            
        Returns:
            VideoOutput 对象
        """
        # 解析尺寸
        width, height = 1280, 720
        if "x" in size:
            parts = size.split("x")
            width, height = int(parts[0]), int(parts[1])
        
        # 计算时长
        duration = num_frames // fps if fps > 0 else 5
        
        # 上传参考图片并获取URL
        ref_image_url = None
        if reference_image_path and os.path.exists(reference_image_path):
            ref_image_url = await self._upload_image(reference_image_path)
        
        # 生成视频
        video_path = await self.generate_video(
            prompt=prompt,
            duration=duration,
            resolution=self._get_resolution(height),
            seed=seed if seed >= 0 else 42,
            reference_image_url=ref_image_url,
        )
        
        return VideoOutput(
            video_path=video_path,
            width=width,
            height=height,
            fps=fps,
            duration=duration,
        )
    
    async def _upload_image(self, image_path: str) -> str:
        """上传图片并返回URL（简化实现）"""
        # 在实际使用中，需要将图片上传到可访问的URL
        # 这里假设图片已经有一个可访问的URL
        # 可以使用本地文件路径或已上传的URL
        return f"file://{os.path.abspath(image_path)}"
    
    def _get_resolution(self, height: int) -> str:
        """根据高度获取分辨率标识"""
        if height <= 480:
            return "480P"
        elif height <= 540:
            return "540P"
        elif height <= 720:
            return "720P"
        elif height <= 1080:
            return "1080P"
        else:
            return "1080P"
    
    async def check_queue_status(self) -> Dict[str, Any]:
        """检查队列状态"""
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/api/v1/queue",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {}
    
    async def get_gpu_status(self) -> List[Dict[str, Any]]:
        """获取GPU状态"""
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/api/v1/gpu",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    return await response.json()
                return []