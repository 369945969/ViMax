#!/bin/bash
# Retry Scene 1 video generation on SkyReels
# Run this when SkyReels GPU issues are resolved

cd "$(dirname "$0")"
source .venv/bin/activate

uv run python -c "
import asyncio
import aiohttp

async def submit():
    base_url = 'http://jackpyf.cloud:9000'
    image_path = '.working_dir/placeholder_images/scene_0.png'
    
    prompt = '将 @图片1 中的[夜晚城市咖啡馆、窗外雨夜霓虹灯、温暖黄灯光、砖墙木桌] 定义为 <场景1>（咖啡馆）。将 @图片1 中的[长发披肩、米色风衣、忧郁眼神女性] 定义为 <主体1>（林晓）。将 @图片1 中的[高大身材、深蓝色西装、湿透男性] 定义为 <主体2>（陈默）。\n\n镜头1：近景固定镜头，<主体1>（林晓）站在窗边，看着窗外淅淅沥沥的雨，玻璃上雨水滑落映着霓虹灯。无台词，<雨声>，<咖啡机嘶嘶声>。\n镜头2：中景固定镜头，咖啡馆门被推开，<主体2>（陈默）走了进来，浑身湿透，雨水顺着发梢滴落，他抬起头，两人都愣住了。林晓说 {陈默？}，音色：女声，青年音色，音调中等，声音轻微颤抖，带惊讶。\n\n古风写实摄影，电影风格，强对比度，极致细节，高清画质，电影质感，画面精美，人物动作自然流畅。'
    
    with open(image_path, 'rb') as f:
        img_data = f.read()
    
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field('task_type', 'reference_to_video')
        data.add_field('prompt', prompt)
        data.add_field('duration', '4')
        data.add_field('resolution', '540P')
        data.add_field('seed', '700')
        data.add_field('offload', 'true')
        data.add_field('ref_imgs', img_data, filename='scene_0.png', content_type='image/png')
        
        async with session.post(f'{base_url}/api/v1/generate', data=data) as resp:
            result = await resp.json()
            task_id = result.get('task_id')
            print(f'任务ID: {task_id}')
            return task_id

task_id = asyncio.run(submit())

async def monitor(task_id):
    for i in range(30):
        await asyncio.sleep(30)
        async with aiohttp.ClientSession() as session:
            async with session.get(f'http://jackpyf.cloud:9000/api/v1/status/{task_id}') as resp:
                d = await resp.json()
                status = d.get('status')
                progress = d.get('progress', 0)
                print(f'[{i+1}] 状态: {status}, 进度: {progress}')
                
                if status == 'completed':
                    async with session.get('http://jackpyf.cloud:9000' + d['download_url']) as v:
                        with open('.working_dir/videos/skyreels_scene1.mp4', 'wb') as f:
                            f.write(await v.read())
                        print('✅ 视频已下载到 .working_dir/videos/skyreels_scene1.mp4')
                    return True
                elif status == 'failed':
                    print(f'❌ 失败 - 错误: {d.get(\"error\", \"未知\")[:100]}')
                    return False
    return False

result = asyncio.run(monitor(task_id))
if not result:
    print('提示: SkyReels 服务器可能仍在维护中，请稍后重试')
"
