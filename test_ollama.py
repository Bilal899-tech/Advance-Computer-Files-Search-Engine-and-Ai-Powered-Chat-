import ollama
from app import Config

print("Testing Ollama connection...")
try:
    config = Config()
    client = ollama.Client(host=config.ollama['host'])
    
    print(f"\nUsing Ollama host: {config.ollama['host']}")
    
    # Test listing models
    print("\n1. Testing model listing...")
    models = client.list()
    print(f"   ✓ Success! Found {len(models['models'])} models")
    
    # Test embedding
    print("\n2. Testing embedding...")
    embedding = client.embeddings(model='all-minilm:l6-v2', prompt='Hello world!')
    print(f"   ✓ Success! Embedding created: {len(embedding['embedding'])} dimensions")
    
    # Test chat
    print("\n3. Testing chat...")
    response = client.generate(model='qwen2.5:3b', prompt='Hello!')
    print(f"   ✓ Success! Response: {response['response'][:50]}...")
    
    print("\n🎉 All tests passed! Ollama is working perfectly!")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()