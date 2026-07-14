import asyncio
import os
import yaml
from langchain.chat_models import init_chat_model

from agents.novel_compressor import NovelCompressor
from agents.event_extractor import EventExtractor
from agents.scene_extractor import SceneExtractor
from agents.global_information_planner import GlobalInformationPlanner
from pipelines.novel2movie_pipeline import Novel2MoviePipeline
from pipelines.script2video_pipeline import Script2VideoPipeline
from tools.render_backend import RenderBackend
from utils.provider_presets import resolve_chat_model_config


# 配置文件路径
AGENT_CONFIG_PATH = "configs/agent.local.yaml"
NOVEL_CONFIG_PATH = "configs/script2video.yaml"


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main():
    print("=" * 80)
    print("🎬 ViMax - Novel to Movie Pipeline".center(80))
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
    novel_config = load_config(NOVEL_CONFIG_PATH)
    
    # 检查必要的API密钥
    llm_config = agent_config.get("llm", {})
    if llm_config.get("api_key") == "" or llm_config.get("api_key") is None:
        print("❌ 请先配置 configs/agent.local.yaml 中的 LLM API 密钥")
        print("   需要填写: llm.model, llm.base_url, llm.api_key")
        return
    
    # 3. 初始化模型
    print("🤖 初始化 LLM 模型...")
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
    
    # EventExtractor
    event_extractor = EventExtractor(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        chat_model=llm_config["model"],
    )
    
    # SceneExtractor
    scene_extractor = SceneExtractor(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        chat_model=llm_config["model"],
    )
    
    # GlobalInformationPlanner
    global_information_planner = GlobalInformationPlanner(
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
        chat_model=llm_config["model"],
    )
    
    # 5. 初始化 Embedding 和 Reranker (用于 RAG)
    print("🔍 初始化 Embedding 和 Reranker...")
    
    embedding_config = agent_config.get("embedding", {})
    reranker_config = agent_config.get("reranker", {})
    
    # 检查 embedding 配置
    if embedding_config.get("api_key") == "" or embedding_config.get("api_key") is None:
        print("⚠️  Embedding 未配置，使用 LLM 配置作为 fallback")
        embedding_config = llm_config
    
    # 检查 reranker 配置
    if reranker_config.get("api_key") == "" or reranker_config.get("api_key") is None:
        print("⚠️  Reranker 未配置，将跳过 RAG 检索")
        # 创建一个简单的 mock reranker
        class MockReranker:
            async def __call__(self, documents, query, top_n=10):
                return [(doc, 1.0) for doc in documents[:top_n]]
        reranker = MockReranker()
    else:
        # TODO: 初始化真实的 reranker
        class MockReranker:
            async def __call__(self, documents, query, top_n=10):
                return [(doc, 1.0) for doc in documents[:top_n]]
        reranker = MockReranker()
    
    # 初始化 embeddings
    from langchain_openai import OpenAIEmbeddings
    embeddings = OpenAIEmbeddings(
        model=embedding_config.get("model", "text-embedding-3-small"),
        api_key=embedding_config.get("api_key", llm_config["api_key"]),
        base_url=embedding_config.get("base_url", llm_config["base_url"]),
    )
    
    # 6. 创建 Novel2Movie Pipeline (仅文本规划模式)
    print("📝 创建 Novel2Movie Pipeline (文本规划模式)...")
    working_dir = ".working_dir/novel2video"
    os.makedirs(working_dir, exist_ok=True)
    
    # 使用 Mock 图像生成器 (仅用于文本规划，不生成实际图像)
    class MockImageGenerator:
        async def generate_single_image(self, prompt, size="512x512", reference_image_paths=None):
            from PIL import Image
            # 创建一个空白图像作为占位符
            img = Image.new('RGB', (512, 512), color='white')
            return img
    
    # 使用 Mock 视频生成器
    class MockVideoGenerator:
        pass
    
    pipeline = Novel2MoviePipeline(
        novel_compressor=novel_compressor,
        event_extractor=event_extractor,
        embeddings=embeddings,
        rerank_model=reranker,
        scene_extractor=scene_extractor,
        global_information_planner=global_information_planner,
        image_generator=MockImageGenerator(),
        rewriter=lambda x: x,  # 简单的 identity rewriter
        script2video_pipeline=None,  # 暂不使用视频生成
        working_dir=working_dir,
    )
    
    # 7. 运行 Pipeline (仅文本规划)
    print("\n🚀 开始处理小说 (文本规划)...")
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
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())