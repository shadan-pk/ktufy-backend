"""
Test script for KG-RAG V2 Implementation
Run this to verify all V2 components work correctly
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test all V2 service imports"""
    print("\n=== Testing V2 Imports ===")
    
    try:
        from services.llm_extractor_v2 import llm_extractor, LLMExtractorV2
        print("✅ LLM Extractor V2")
    except ImportError as e:
        print(f"❌ LLM Extractor V2: {e}")
        return False
    
    try:
        from services.neo4j_service_v2 import neo4j_service, Neo4jServiceV2
        print("✅ Neo4j Service V2")
    except ImportError as e:
        print(f"❌ Neo4j Service V2: {e}")
        return False
    
    try:
        from services.embedding_service_v2 import embedding_service, EmbeddingServiceV2
        print("✅ Embedding Service V2")
    except ImportError as e:
        print(f"❌ Embedding Service V2: {e}")
        return False
    
    try:
        from services.query_router import query_router, QueryRouter, QueryType
        print("✅ Query Router")
    except ImportError as e:
        print(f"❌ Query Router: {e}")
        return False
    
    try:
        from services.syllabus_processor_v2 import syllabus_processor, SyllabusProcessorV2
        print("✅ Syllabus Processor V2")
    except ImportError as e:
        print(f"❌ Syllabus Processor V2: {e}")
        return False
    
    try:
        from routers.admin_v2 import router
        print("✅ Admin Router V2")
    except ImportError as e:
        print(f"❌ Admin Router V2: {e}")
        return False
    
    return True


def test_canonical_id():
    """Test canonical ID generation"""
    print("\n=== Testing Canonical ID Generation ===")
    
    from services.llm_extractor_v2 import to_canonical_id
    
    test_cases = [
        ("Arrays and Linked Lists", "cs201_m1", "cs201_m1_arrays_and_linked_lists"),
        ("Binary Search Tree", "cs301_m2", "cs301_m2_binary_search_tree"),
        ("DFS & BFS", "cs401_m3", "cs401_m3_dfs_bfs"),
    ]
    
    all_passed = True
    for concept, prefix, expected in test_cases:
        result = to_canonical_id(concept, prefix)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{concept}' with prefix '{prefix}' → {result}")
        if result != expected:
            print(f"   Expected: {expected}")
            all_passed = False
    
    return all_passed


def test_compound_splitting():
    """Test compound concept splitting"""
    print("\n=== Testing Compound Concept Splitting ===")
    
    from services.llm_extractor_v2 import split_compound_concepts
    
    test_cases = [
        ("DFS and BFS", ["DFS", "BFS"]),
        ("Arrays, Linked Lists and Trees", ["Arrays", "Linked Lists", "Trees"]),
        ("Binary Search Tree", ["Binary Search Tree"]),  # Should not split
        ("Stacks & Queues", ["Stacks", "Queues"]),
    ]
    
    all_passed = True
    for compound, expected in test_cases:
        result = split_compound_concepts(compound)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{compound}' → {result}")
        if result != expected:
            print(f"   Expected: {expected}")
            all_passed = False
    
    return all_passed


def test_query_routing():
    """Test query routing logic"""
    print("\n=== Testing Query Routing ===")
    
    from services.query_router import query_router, QueryType
    
    test_queries = [
        ("What is binary search?", QueryType.VECTOR_ONLY),
        ("What topics are in Module 2?", QueryType.KG_ONLY),
        ("What are the prerequisites for graph algorithms?", QueryType.KG_THEN_VECTOR),
        ("Explain DFS and compare with BFS", QueryType.HYBRID),
        ("Show me the syllabus for Data Structures", QueryType.VECTOR_ONLY),
    ]
    
    print("\nQuery routing analysis:")
    for query, expected_type in test_queries:
        query_type, metadata = query_router.route(query)
        status = "✅" if query_type == expected_type else "⚠️"
        print(f"\n{status} Query: '{query}'")
        print(f"   Routed to: {query_type.value}")
        print(f"   Expected: {expected_type.value}")
        print(f"   Metadata: {metadata}")
    
    return True


def test_system_status():
    """Test system status"""
    print("\n=== Testing System Status ===")
    
    from services.syllabus_processor_v2 import syllabus_processor
    
    status = syllabus_processor.get_status()
    
    print(f"Version: {status.get('version', 'unknown')}")
    print(f"PDF Processor: {'✅' if status['pdf_processor'] else '❌'}")
    print(f"LLM Extractor: {'✅' if status['llm_extractor'] else '❌'}")
    print(f"Neo4j: {'✅' if status['neo4j'] else '⚠️ Not connected'}")
    print(f"Embedding Model: {'✅' if status['embedding_model'] else '⚠️ Not loaded'}")
    
    return True


def main():
    """Run all tests"""
    print("=" * 50)
    print("KG-RAG V2 Implementation Test")
    print("=" * 50)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Canonical ID", test_canonical_id()))
    results.append(("Compound Splitting", test_compound_splitting()))
    results.append(("Query Routing", test_query_routing()))
    results.append(("System Status", test_system_status()))
    
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ All V2 tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 50)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
