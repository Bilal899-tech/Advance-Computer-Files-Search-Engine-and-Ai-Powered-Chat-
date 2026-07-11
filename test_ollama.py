from core import LLMClient, Config

print("Testing hybrid provider system (SPUR API → local Ollama fallback)...")
try:
    config = Config()
    client = LLMClient()
    
    # Test listing models (auto-detects available provider)
    print("\n1. Testing provider detection...")
    models = client.list()
    provider = client.active_provider
    print(f"   ✓ Active provider: {provider.upper()}")
    
    # Test embedding
    print("\n2. Testing embedding...")
    fallback_emb = config.models.get('embedding', 'all-minilm:l6-v2')
    embedding = client.embeddings(model='text-embedding-3-small', fallback_model=fallback_emb, prompt='Hello world!')
    print(f"   ✓ Embedding created: {len(embedding['embedding'])} dimensions (provider: {client.active_provider})")
    
    # Test chat
    print("\n3. Testing chat...")
    fallback_chat = config.models.get('chat_fallback', 'qwen2.5:3b')
    response = client.generate(model=config.models['chat'], fallback_model=fallback_chat, prompt='Hello!')
    print(f"   ✓ Response: {response['response'][:50]}... (provider: {client.active_provider})")
    
    print("\n🎉 All tests passed! Hybrid fallback system is working!")
    print(f"   Current provider: {client.active_provider.upper()}")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()