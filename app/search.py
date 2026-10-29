"""Optional Elasticsearch adapter. Requires indexed terms and real query embeddings.

This adapter does not silently fall back to the rule-based demo search.
Both lexical and vector searches enforce every nested category constraint.
"""
import httpx


def filters(categories, max_spend=None):
    clauses = [{"nested": {"path": "benefits", "query": {"term": {"benefits.category": category}}}} for category in categories]
    if max_spend is not None:
        clauses.append({"range": {"threshold": {"lte": max_spend}}})
    return clauses


def rrf(*rankings, k=60):
    scores, documents = {}, {}
    for ranking in rankings:
        seen = set()
        for rank, hit in enumerate(ranking, 1):
            key = hit["_id"]
            if key in seen:
                continue
            seen.add(key)
            documents[key] = hit["_source"]
            scores[key] = scores.get(key, 0) + 1 / (k + rank)
    return [{"id": key, "score": scores[key], "card": documents[key]} for key in sorted(scores, key=lambda key: (-scores[key], key))]


def hybrid_search(url, query, query_vector, categories, max_spend=None, client=None):
    if not query_vector or not categories:
        raise ValueError("query_vector and required categories are required")
    condition = filters(categories, max_spend)
    def run(http):
        lexical = http.post(url.rstrip('/') + '/cards/_search', json={"size": 30, "query": {"bool": {
            "must": [{"match": {"description": query}}], "filter": condition}}})
        lexical.raise_for_status()
        vector = http.post(url.rstrip('/') + '/cards/_search', json={"size": 30, "knn": {
            "field": "embedding", "query_vector": query_vector, "k": 30, "num_candidates": 100,
            "filter": {"bool": {"filter": condition}}}})
        vector.raise_for_status()
        # Recheck all must-have categories before returning fused candidates.
        return [hit for hit in rrf(lexical.json()['hits']['hits'], vector.json()['hits']['hits'])
                if set(categories).issubset({b['category'] for b in hit['card']['benefits']})
                and (max_spend is None or hit['card']['threshold'] <= max_spend)]
    if client is not None:
        return run(client)
    with httpx.Client(timeout=30) as http:
        return run(http)
