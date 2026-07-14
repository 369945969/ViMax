import asyncio
import json
import os
import yaml
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from tools.video_generator_skyreels_api import VideoGeneratorSkyReels


def load_config():
    with open("configs/agent.local.yaml") as f:
        return yaml.safe_load(f)


def create_placeholder_image(scene: dict, output_path: str) -> str:
    """创建占位图片"""
    # 创建一个简单的占位图片
    img = Image.new('RGB', (1280, 720), color=(30, 30, 40))
    draw = ImageDraw.Draw(img)
    
    # 绘制场景信息
    env = scene.get("environment", {})
    slugline = env.get("slugline", "场景")
    description = env.get("description", "")[:100]
    
    # 绘制文字
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        font = ImageFont.load_default()
        font_small = font
    
    # 绘制标题
    draw.text((50, 50), slugline, fill="white", font=font)
    
    # 绘制描述
    if description:
        draw.text((50, 100), description[:80], fill=(180, 180, 180), font=font_small)
    
    # 绘制装饰线
    draw.line([(50, 150), (1230, 150)], fill=(100, 100, 100), width=2)
    
    # 绘制人物信息
    characters = scene.get("characters", [])
    y = 180
    for char in characters:
        name = char.get("identifier_in_scene", "角色")
        features = char.get("static_features", "")[:60]
        draw.text((50, y), f"• {name}: {features}", fill=(200, 200, 200), font=font_small)
        y += 30
    
    img.save(output_path)
    return output_path


async def upload_image_to_url(image_path: str) -> str:
    """将本地图片转换为data URL"""
    import base64
    with open(image_path, "rb") as f:
        img_data = f.read()
    b64_data = base64.b64encode(img_data).decode('utf-8')
    return f"data:image/png;base64,{b64_data}"


def scene_to_video_prompt(scene: dict, style: str = "电影风格") -> str:
    """将场景转换为视频生成提示词"""
    env = scene["environment"]
    characters = scene["characters"]
    script = scene["script"]
    
    # 构建角色描述
    char_desc_parts = []
    for i, char in enumerate(characters):
        desc = f"人物{i+1}（{char['identifier_in_scene']}）：{char.get('static_features', '')} {char.get('dynamic_features', '')}"
        char_desc_parts.append(desc)
    char_desc = "；".join(char_desc_parts)
    
    # 构建场景描述
    scene_desc = f"{env.get('slugline', '')}。{env.get('description', '')}"
    
    # 从script提取关键动作
    action_lines = []
    for line in script.split("\n"):
        line = line.strip()
        if not line:
            continue
        # 去掉角色名标记
        clean = line.replace("<", "").replace(">", "")
        if len(clean) > 5:
            action_lines.append(clean)
    
    action_text = "。".join(action_lines[:5])  # 取前5行
    
    # 组合提示词
    prompt = f"""将参考图中的场景定义为画面背景。

{scene_desc}

{char_desc}

镜头内容：{action_text}

{style}，高清画质，电影质感，画面精美，人物动作自然流畅。"""
    
    return prompt


async def monitor_and_download(gen: VideoGeneratorSkyReels, task_ids: list):
    """监控任务并下载完成的视频"""
    import time
    
    print("\n" + "=" * 80)
    print("🔍 开始监控任务进度...".center(80))
    print("=" * 80)
    
    video_dir = ".working_dir/videos"
    os.makedirs(video_dir, exist_ok=True)
    
    pending_tasks = {t["task_id"]: t for t in task_ids if t.get("task_id")}
    completed_videos = []
    
    while pending_tasks:
        print(f"\n⏳ 剩余任务: {len(pending_tasks)}")
        
        for task_id, task_info in list(pending_tasks.items()):
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {}
                    if gen.api_key:
                        headers["X-API-Key"] = gen.api_key
                    
                    async with session.get(
                        f"{gen.base_url}/api/v1/status/{task_id}",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as response:
                        if response.status != 200:
                            continue
                        
                        status_data = await response.json()
                        status = status_data.get("status", "")
                        progress = status_data.get("progress", 0)
                        
                        if status == "completed":
                            print(f"\n✅ 任务完成: {task_id}")
                            print(f"   场景: {task_info['scene']}")
                            
                            # 下载视频
                            download_url = status_data.get("download_url")
                            if download_url:
                                video_path = await gen._download_video(session, download_url, task_id, headers)
                                completed_videos.append({
                                    "scene": task_info["scene"],
                                    "task_id": task_id,
                                    "video_path": video_path
                                })
                            del pending_tasks[task_id]
                        
                        elif status == "failed":
                            error = status_data.get("error", "未知错误")
                            print(f"\n❌ 任务失败: {task_id}")
                            print(f"   错误: {error}")
                            del pending_tasks[task_id]
                        
                        else:
                            print(f"   {task_id}: {status} ({progress*100:.1f}%)")
            
            except Exception as e:
                print(f"   ⚠️ 查询失败: {task_id}: {e}")
        
        if pending_tasks:
            print(f"\n💤 等待30秒后重试...")
            await asyncio.sleep(30)
    
    # 保存结果
    result_file = ".working_dir/completed_videos.json"
    with open(result_file, "w") as f:
        json.dump(completed_videos, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print(f"🎉 全部完成! 共下载 {len(completed_videos)} 个视频".center(80))
    print("=" * 80)
    
    for v in completed_videos:
        print(f"   📹 {v['scene']} -> {v['video_path']}")
    
    return completed_videos


async def main():
    print("=" * 80)
    print("🎬 小说场景视频生成".center(80))
    print("=" * 80)
    
    # 加载配置
    config = load_config()
    video_config = config.get("video", {})
    skyreels_config = video_config.get("skyreels", {})
    
    # 初始化视频生成器
    gen = VideoGeneratorSkyReels(
        api_key=skyreels_config.get("api_key", ""),
        base_url=skyreels_config.get("base_url", "http://jackpyf.cloud:9000"),
        timeout=600,
    )
    
    # 加载场景
    scenes_dir = ".working_dir/novel2video/scenes"
    all_scenes = []
    
    for event_dir in sorted(os.listdir(scenes_dir)):
        event_path = os.path.join(scenes_dir, event_dir)
        if not os.path.isdir(event_path):
            continue
        for scene_file in sorted(os.listdir(event_path)):
            if scene_file.endswith(".json"):
                with open(os.path.join(event_path, scene_file)) as f:
                    scene = json.load(f)
                    scene["_event"] = event_dir
                    scene["_file"] = scene_file
                    all_scenes.append(scene)
    
    print(f"\n📖 找到 {len(all_scenes)} 个场景")
    
    # 只处理有参考图片的场景
    placeholder_dir = ".working_dir/placeholder_images"
    
    # 为每个场景生成视频
    video_style = "古风写实摄影，电影风格，强对比度，极致细节"
    results = []
    
    for i, scene in enumerate(all_scenes):
        # 检查是否有参考图片
        placeholder_path = os.path.join(placeholder_dir, f"scene_{i}.png")
        if not os.path.exists(placeholder_path):
            print(f"\n⚠️ 跳过场景 {i+1}: 没有参考图片 {placeholder_path}")
            continue
        
        print(f"\n{'='*60}")
        print(f"🎬 场景 {i+1}/{len(all_scenes)}: {scene['_event']}/{scene['_file']}")
        print(f"📍 场景: {scene['environment'].get('slugline', '未知')}")
        print(f"🖼️  参考图片: {placeholder_path}")
        
        # 生成提示词
        prompt = scene_to_video_prompt(scene, video_style)
        print(f"\n📝 提示词:")
        print(f"   {prompt[:150]}...")
        
        # 计算时长（根据script长度）
        script_len = len(scene.get("script", ""))
        duration = min(max(script_len // 50, 4), 10)
        
        print(f"\n⏳ 提交视频生成任务 (时长: {duration}秒)...")
        
        try:
            # 读取图片数据
            with open(placeholder_path, "rb") as f:
                img_data = f.read()
            
            # 提交任务 - 使用ref_imgs字段
            async with aiohttp.ClientSession() as session:
                headers = {}
                if gen.api_key:
                    headers["X-API-Key"] = gen.api_key
                
                data = aiohttp.FormData()
                data.add_field("task_type", "reference_to_video")
                data.add_field("prompt", prompt)
                data.add_field("duration", str(duration))
                data.add_field("resolution", "540P")
                data.add_field("seed", str(42 + i))
                data.add_field("offload", "true")
                
                # 使用ref_imgs字段上传图片数组
                data.add_field(
                    "ref_imgs",
                    img_data,
                    filename=f"scene_{i}.png",
                    content_type="image/png"
                )
                
                async with session.post(
                    f"{gen.base_url}/api/v1/generate",
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status != 202:
                        error_text = await response.text()
                        raise Exception(f"提交任务失败: {response.status} - {error_text}")
                    result = await response.json()
                    task_id = result.get("task_id")
                    print(f"✅ 任务已提交: {task_id}")
                    results.append({
                        "scene": f"{scene['_event']}/{scene['_file']}",
                        "task_id": task_id,
                        "status": "submitted"
                    })
        except Exception as e:
            print(f"❌ 提交失败: {e}")
            results.append({
                "scene": f"{scene['_event']}/{scene['_file']}",
                "task_id": None,
                "status": "failed",
                "error": str(e)
            })
    
    # 保存任务信息
    tasks_file = ".working_dir/video_tasks.json"
    with open(tasks_file, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print(f"✅ 任务提交完成!")
    print(f"📋 任务信息已保存到: {tasks_file}")
    print("=" * 80)
    
    # 监控并下载
    await monitor_and_download(gen, results)
    
    return results


if __name__ == "__main__":
    asyncio.run(main())