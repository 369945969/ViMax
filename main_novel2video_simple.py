import asyncio
import os
import yaml
from langchain.chat_models import init_chat_model

from agents.novel_compressor import NovelCompressor
from agents.event_extractor import EventExtractor
from agents.scene_extractor import SceneExtractor
from agents.global_information_planner import GlobalInformationPlanner
from pipelines.novel2movie_pipeline import Novel2MoviePipeline
from tools.video_generator_skyreels_api import VideoGeneratorSkyReels


# 配置文件路径
AGENT_CONFIG_PATH = "configs/agent.local.yaml"


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class MockReranker:
    """Mock reranker - 跳过向量化，直接返回所有文档"""
    async def __call__(self, documents, query, top_n=10):
        return [(doc, 1.0) for doc in documents[:top_n]]


class MockEmbeddings:
    """Mock embeddings - 不使用真正的向量化"""
    def __init__(self):
        self.model = "mock"
    
    def embed_documents(self, texts):
        return [[0.0] * 384 for _ in texts]
    
    def embed_query(self, text):
        return [0.0] * 384


class MockImageGenerator:
    """Mock 图像生成器 - 仅用于文本规划"""
    async def generate_single_image(self, prompt, size="512x512", reference_image_paths=None):
        from PIL import Image
        img = Image.new('RGB', (512, 512), color='white')
        return img


async def main():
    print("=" * 80)
    print("🎬 ViMax - Novel to Movie Pipeline (简化版 - 无向量化)".center(80))
    print("=" * 80)
    
    # 1. 读取小说文件
    novel_path = "novel.txt"
    if not os.path.exists(novel_path):
        print(f"❌ 小说文件不存在: {novel_path}")
        return
    
    with open(novel_path, "r", encoding="utf-8") as f:
        novel_text = f.read()
    
    print(f"📖 已读取小说: {novel_path}")
    print(f"📝 小说长度: {len(novel_text)} 字符")
    
    # 2. 加载配置
    print("\n🔧 加载配置...")
    agent_config = load_config(AGENT_CONFIG_PATH)
    
    # 检查必要的API密钥
    llm_config = agent_config.get("llm", {})
    if llm_config.get("api_key") == "" or llm_config.get("api_key") is None:
        print("❌ 请先配置 configs/agent.local.yaml 中的 LLM API 密钥")
        print("   需要填写: llm.model, llm.base_url, llm.api_key")
        return
    
    # 3. 初始化模型
    print("🤖 初始化 LLM 模型...")
    print(f"   模型: {llm_config['model']}")
    print(f"   地址: {llm_config['base_url']}")
    
    llm_model = init_chat_model(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        model_provider="openai",
    )
    
    # 4. 初始化 Agents
    print("👥 初始化 Agents...")
    
    # NovelCompressor
    novel_compressor = NovelCompressor(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        chat_model=llm_config["model"],
    )
    print("   ✓ NovelCompressor")
    
    # EventExtractor
    event_extractor = EventExtractor(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        chat_model=llm_config["model"],
    )
    print("   ✓ EventExtractor")
    
    # SceneExtractor
    scene_extractor = SceneExtractor(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        chat_model=llm_config["model"],
    )
    print("   ✓ SceneExtractor")
    
    # GlobalInformationPlanner
    global_information_planner = GlobalInformationPlanner(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        chat_model=llm_config["model"],
    )
    print("   ✓ GlobalInformationPlanner")
    
    # 5. 使用 Mock Embeddings 和 Reranker (跳过向量化)
    print("🔍 使用简化模式 (跳过向量化)...")
    embeddings = MockEmbeddings()
    reranker = MockReranker()
    print("   ✓ MockEmbeddings (不使用向量化)")
    print("   ✓ MockReranker (跳过重排序)")
    
    # 6. 初始化视频生成器
    print("🎬 初始化视频生成器...")
    video_config = agent_config.get("video", {})
    video_provider = video_config.get("provider", "skyreels")
    
    if video_provider == "skyreels":
        skyreels_config = video_config.get("skyreels", {})
        video_generator = VideoGeneratorSkyReels(
            api_key=skyreels_config.get("api_key", ""),
            base_url=skyreels_config.get("base_url", "http://jackpyf.cloud:9000"),
            timeout=skyreels_config.get("timeout", 300),
        )
        print("   ✓ SkyReels V3 视频生成器")
        print(f"   地址: {skyreels_config.get('base_url', 'http://jackpyf.cloud:9000')}")
    else:
        print("   ⚠️ 未配置视频生成器，将跳过视频生成")
        video_generator = None
    
    # 7. 创建 Novel2Movie Pipeline
    print("📝 创建 Novel2Movie Pipeline...")
    working_dir = ".working_dir/novel2video"
    os.makedirs(working_dir, exist_ok=True)
    
    pipeline = Novel2MoviePipeline(
        novel_compressor=novel_compressor,
        event_extractor=event_extractor,
        embeddings=embeddings,
        rerank_model=reranker,
        scene_extractor=scene_extractor,
        global_information_planner=global_information_planner,
        image_generator=MockImageGenerator(),
        rewriter=lambda x: x,
        script2video_pipeline=None,
        working_dir=working_dir,
    )
    print("   ✓ Pipeline 创建完成")
    
    # 8. 运行 Pipeline (仅文本规划)
    print("\n🚀 开始处理小说...")
    print("=" * 80)
    
    # 设置风格
    style = "cinematic, movie style, high quality"
    
    # 运行文本规划
    result = await pipeline.plan_text_artifacts(
        novel_text=novel_text,
        style=style,
    )
    
    print("\n" + "=" * 80)
    print("✅ 小说文本规划完成!")
    print(f"📁 输出目录: {working_dir}")
    print("\n📊 处理结果:")
    print(f"   - 压缩后文本长度: {len(result['compressed_novel'])} 字符")
    print(f"   - 提取的事件数量: {len(result['events'])}")
    print(f"   - 场景数量: {sum(len(scenes) for scenes in result['scenes'].values())}")
    print(f"   - 角色数量: {len(result['characters_in_novel'])}")
    print("\n📁 生成的文件:")
    print(f"   - {working_dir}/novel/novel.txt (原始小说)")
    print(f"   - {working_dir}/novel/novel_compressed.txt (压缩后)")
    print(f"   - {working_dir}/events/ (事件文件)")
    print(f"   - {working_dir}/scenes/ (场景文件)")
    print(f"   - {working_dir}/global_information/characters/ (角色信息)")
    
    # 显示生成的场景脚本示例
    if result['scenes']:
        first_event_scenes = list(result['scenes'].values())[0]
        if first_event_scenes:
            print("\n📝 场景脚本示例:")
            scene = first_event_scenes[0]
            print(f"   场景 {scene.idx}: {scene.script[:200]}...")
    
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())