import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse


class VideoHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        # 视频列表页面
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html = self.generate_index_html()
            self.wfile.write(html.encode('utf-8'))
            return
        
        # API: 获取视频列表
        if self.path == '/api/videos':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            videos = self.get_video_list()
            self.wfile.write(json.dumps(videos, ensure_ascii=False).encode('utf-8'))
            return
        
        # 视频文件服务
        if self.path.startswith('/videos/'):
            video_path = self.path[8:]  # 去掉 /videos/
            video_full_path = os.path.join('.working_dir/videos', video_path)
            
            if os.path.exists(video_full_path):
                self.send_response(200)
                self.send_header('Content-type', 'video/mp4')
                self.send_header('Content-Length', str(os.path.getsize(video_full_path)))
                self.end_headers()
                
                with open(video_full_path, 'rb') as f:
                    self.wfile.write(f.read())
                return
        
        # 场景信息API
        if self.path.startswith('/api/scene/'):
            scene_id = self.path[11:]
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            scene_data = self.get_scene_data(scene_id)
            self.wfile.write(json.dumps(scene_data, ensure_ascii=False).encode('utf-8'))
            return
        
        self.send_error(404)
    
    def get_video_list(self):
        """获取视频列表"""
        videos = []
        video_dir = '.working_dir/videos'
        
        if os.path.exists(video_dir):
            for f in os.listdir(video_dir):
                if f.endswith('.mp4'):
                    # 尝试关联场景信息
                    scene_info = self.find_scene_for_video(f)
                    videos.append({
                        'filename': f,
                        'path': f'/videos/{f}',
                        'scene': scene_info.get('scene', '未知场景'),
                        'description': scene_info.get('description', '')
                    })
        
        return videos
    
    def find_scene_for_video(self, video_filename):
        """根据视频文件名查找对应的场景信息"""
        # 尝试从completed_videos.json获取信息
        completed_file = '.working_dir/completed_videos.json'
        if os.path.exists(completed_file):
            with open(completed_file) as f:
                completed = json.load(f)
                for v in completed:
                    if video_filename in v.get('video_path', ''):
                        return {'scene': v.get('scene', ''), 'description': ''}
        
        return {'scene': video_filename, 'description': ''}
    
    def get_scene_data(self, scene_id):
        """获取场景详细数据"""
        scenes_dir = '.working_dir/novel2video/scenes'
        
        # 解析scene_id (例如: event_0/scene_0)
        parts = scene_id.split('/')
        if len(parts) == 2:
            event_dir, scene_file = parts
            scene_path = os.path.join(scenes_dir, event_dir, f'{scene_file}.json')
            
            if os.path.exists(scene_path):
                with open(scene_path) as f:
                    return json.load(f)
        
        return {'error': 'Scene not found'}
    
    def generate_index_html(self):
        """生成主页HTML"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ViMax - 小说转短剧</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header {
            text-align: center;
            padding: 40px 0;
            background: linear-gradient(135deg, #16213e 0%, #0f3460 100%);
            margin-bottom: 30px;
        }
        h1 { font-size: 2.5em; margin-bottom: 10px; }
        .subtitle { color: #aaa; font-size: 1.2em; }
        .video-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }
        .video-card {
            background: #16213e;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            transition: transform 0.3s;
        }
        .video-card:hover { transform: translateY(-5px); }
        .video-player {
            width: 100%;
            aspect-ratio: 16/9;
            background: #000;
        }
        .video-info {
            padding: 15px;
        }
        .video-title {
            font-size: 1.1em;
            font-weight: bold;
            margin-bottom: 8px;
        }
        .video-desc {
            color: #aaa;
            font-size: 0.9em;
            line-height: 1.4;
        }
        .no-video {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        .no-video h2 { margin-bottom: 15px; }
        .badge {
            display: inline-block;
            background: #e94560;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>🎬 ViMax - 小说转短剧</h1>
            <p class="subtitle">《雨夜重逢》 - 由 SkyReels V3 生成</p>
        </div>
    </header>
    
    <div class="container">
        <div id="content">
            <p style="text-align: center; color: #666;">加载中...</p>
        </div>
    </div>
    
    <script>
        async function loadVideos() {
            try {
                const response = await fetch('/api/videos');
                const videos = await response.json();
                
                const content = document.getElementById('content');
                
                if (videos.length === 0) {
                    content.innerHTML = `
                        <div class="no-video">
                            <h2>暂无视频</h2>
                            <p>请先运行视频生成脚本：<br><code>uv run python generate_scene_videos.py</code></p>
                        </div>
                    `;
                    return;
                }
                
                let html = '<div class="video-grid">';
                videos.forEach(video => {
                    html += `
                        <div class="video-card">
                            <video class="video-player" controls>
                                <source src="${video.path}" type="video/mp4">
                                您的浏览器不支持视频播放。
                            </video>
                            <div class="video-info">
                                <div class="badge">SkyReels V3</div>
                                <div class="video-title">${video.scene}</div>
                                <div class="video-desc">${video.description || 'AI生成的视频片段'}</div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                
                content.innerHTML = html;
            } catch (error) {
                console.error('加载视频失败:', error);
            }
        }
        
        loadVideos();
    </script>
</body>
</html>'''


def main():
    port = 8080
    server = HTTPServer(('0.0.0.0', port), VideoHandler)
    
    print("=" * 60)
    print("🎬 ViMax 视频播放服务器".center(60))
    print("=" * 60)
    print(f"\n🌐 服务器已启动: http://localhost:{port}")
    print(f"📁 视频目录: .working_dir/videos/")
    print("\n按 Ctrl+C 停止服务器")
    print("=" * 60)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.shutdown()


if __name__ == '__main__':
    main()