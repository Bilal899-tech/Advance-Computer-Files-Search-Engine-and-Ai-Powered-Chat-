import json
import time
import os
from core import Config, VectorStore, Database, DocumentProcessor, LLMClient
from datetime import datetime

def score_response(response, expected_keywords):
    """Score the response based on keyword matching."""
    response_lower = response.lower()
    keywords_lower = [kw.lower() for kw in expected_keywords]
    
    matches = sum(1 for kw in keywords_lower if kw in response_lower)
    total_keywords = len(keywords_lower)
    
    if total_keywords == 0:
        return 0.0
    
    score = matches / total_keywords
    return score

def run_evaluation():
    config = Config()
    
    print("=" * 80)
    print("PDF CHAT ASSISTANT - STRUCTURED EVALUATION")
    print("=" * 80)
    print(f"\nUsing SPUR API endpoint: {os.getenv('OPENAI_BASE_URL', 'https://ai.spuric.com/v1')}")
    print("\nInitializing...")
    
    # Load test PDF if not already loaded
    db = Database(config.paths['database'])
    existing_docs = db.get_documents()
    pdf_found = any("sample_report.pdf" in doc[0] for doc in existing_docs)
    
    client = LLMClient()
    
    if not pdf_found:
        print("\nAdding test PDF document...")
        test_pdf_path = "data/test_documents/sample_report.pdf"
        if os.path.exists(test_pdf_path):
            doc_processor = DocumentProcessor(config)
            all_chunks, all_metadata, filetype = doc_processor.process_file(test_pdf_path)
            
            vector_store = VectorStore(config)
            if all_chunks:
                vector_store.add_chunks(all_chunks, all_metadata)
                db.add_document("sample_report.pdf", test_pdf_path, filetype, len(all_chunks))
                db.update_system_stats(vector_store.get_chunk_count())
            
            print(f"Test PDF processed: {len(all_chunks)} chunks created")
        else:
            print(f"Warning: Test PDF not found at {test_pdf_path}")
    else:
        print("\nTest PDF already loaded")
    
    vector_store = VectorStore(config)
    
    with open('evals/dataset.json', 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    
    results = {
        "metadata": dataset["metadata"],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {},
        "evaluation_results": []
    }
    
    total_score = 0.0
    total_time = 0.0
    pass_count = 0
    fail_count = 0
    
    category_scores = {}
    type_scores = {}
    difficulty_scores = {}
    
    print(f"\nStarting evaluation of {len(dataset['evaluation_cases'])} test cases...")
    print("-" * 80)
    
    for case in dataset['evaluation_cases']:
        print(f"\n[{case['id']}] Question: {case['question']}")
        print(f"      Type: {case['type']} | Difficulty: {case['difficulty']} | Category: {case['category']}")
        
        start_time = time.time()
        search_results, _ = vector_store.search(case['question'])
        
        context = ""
        if search_results:
            context = "Context from PDFs:\n"
            for result in search_results:
                context += f"\n[From {result['pdf_name']}, Page {result['page']}]:\n{result['chunk']}\n"
        
        prompt = f"You are a helpful assistant. Answer the user's question using ONLY the provided context.\nIf you don't find the answer in the context, say \"I don't have information about that in the uploaded PDFs.\"\n\n{context}\n\nUser Question: {case['question']}\nAnswer:"
        
        try:
            fallback_model = config.models.get('chat_fallback', 'qwen2.5:3b')
            response = client.generate(model=config.models['chat'], fallback_model=fallback_model, prompt=prompt)
            ai_response = response['response'].strip()
            end_time = time.time()
            response_time = end_time - start_time
            
            score = score_response(ai_response, case['expected_keywords'])
            passed = score > 0.5
            
            total_score += score
            total_time += response_time
            
            if passed:
                pass_count += 1
                status = "✓ PASS"
            else:
                fail_count += 1
                status = "✗ FAIL"
            
            print(f"      {status} | Score: {score:.2f} | Time: {response_time:.2f}s")
            print(f"      Response: {ai_response[:100]}{'...' if len(ai_response) > 100 else ''}")
            
            result_entry = {
                "id": case['id'],
                "question": case['question'],
                "type": case['type'],
                "difficulty": case['difficulty'],
                "category": case['category'],
                "response": ai_response,
                "expected_keywords": case['expected_keywords'],
                "expected_answer": case['expected_answer'],
                "score": score,
                "response_time": response_time,
                "passed": passed,
                "has_context": len(search_results) > 0
            }
            
            results["evaluation_results"].append(result_entry)
            
            cat = case['category']
            typ = case['type']
            diff = case['difficulty']
            
            if cat not in category_scores:
                category_scores[cat] = {"scores": [], "count": 0}
            category_scores[cat]["scores"].append(score)
            category_scores[cat]["count"] += 1
            
            if typ not in type_scores:
                type_scores[typ] = {"scores": [], "count": 0}
            type_scores[typ]["scores"].append(score)
            type_scores[typ]["count"] += 1
            
            if diff not in difficulty_scores:
                difficulty_scores[diff] = {"scores": [], "count": 0}
            difficulty_scores[diff]["scores"].append(score)
            difficulty_scores[diff]["count"] += 1
            
        except Exception as e:
            print(f"      ✗ Error: {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1
            
            result_entry = {
                "id": case['id'],
                "question": case['question'],
                "type": case['type'],
                "difficulty": case['difficulty'],
                "category": case['category'],
                "error": str(e),
                "score": 0.0,
                "response_time": 0.0,
                "passed": False,
                "has_context": False
            }
            results["evaluation_results"].append(result_entry)
    
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)
    
    total_cases = len(dataset['evaluation_cases'])
    avg_score = total_score / total_cases if total_cases > 0 else 0
    avg_time = total_time / total_cases if total_cases > 0 else 0
    pass_rate = (pass_count / total_cases * 100) if total_cases > 0 else 0
    
    results["summary"] = {
        "total_cases": total_cases,
        "passed": pass_count,
        "failed": fail_count,
        "pass_rate": pass_rate,
        "average_score": avg_score,
        "average_response_time": avg_time,
        "category_scores": {cat: sum(data["scores"]) / len(data["scores"]) for cat, data in category_scores.items()},
        "type_scores": {typ: sum(data["scores"]) / len(data["scores"]) for typ, data in type_scores.items()},
        "difficulty_scores": {diff: sum(data["scores"]) / len(data["scores"]) for diff, data in difficulty_scores.items()}
    }
    
    print(f"\nTotal Test Cases: {total_cases}")
    print(f"Passed: {pass_count} | Failed: {fail_count}")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print(f"Average Score: {avg_score:.2f}")
    print(f"Average Response Time: {avg_time:.2f}s")
    
    print("\nCategory Scores:")
    for cat, score in results["summary"]["category_scores"].items():
        print(f"  {cat}: {score:.2f}")
    
    print("\nType Scores:")
    for typ, score in results["summary"]["type_scores"].items():
        print(f"  {typ}: {score:.2f}")
    
    print("\nDifficulty Scores:")
    for diff, score in results["summary"]["difficulty_scores"].items():
        print(f"  {diff}: {score:.2f}")
    
    with open('evals/results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to evals/results.json")
    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    run_evaluation()
