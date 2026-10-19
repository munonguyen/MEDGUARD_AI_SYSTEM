"""Inspect/seed the candidate pool. Clinical approval belongs to the admin API."""
import argparse, json
from pathlib import Path
from app.knowledge.loader import knowledge
from app.services.knowledge_pool import get_knowledge_pool
from app.services.trusted_evidence import trusted_medical_url


def seed_candidates(pool):
    ids = []
    for item in knowledge.symptom_guidance:
        sources = item.get('source_references', [])
        url = next((u for u in sources if isinstance(u, str) and trusted_medical_url(u)), None)
        if not url:
            continue
        content = json.dumps({k:v for k,v in item.items() if k not in {'keywords','v25_contextual_reasoning'}}, ensure_ascii=False, sort_keys=True)
        if 40 <= len(content) <= 12000:
            ids.append(pool.stage(title=item.get('topic', 'Hướng dẫn lâm sàng').replace('_',' '), content=content,
                                  source_url=url, domain='clinical', actor='seed_existing_curated_policy'))
    path = Path(__file__).resolve().parents[1] / 'app/knowledge/crawled_clinical_guidelines.json'
    for item in json.loads(path.read_text()).get('guidelines', []):
        url = item.get('source_uri', '')
        content = item.get('content', '')
        if trusted_medical_url(url) and 40 <= len(content) <= 12000:
            ids.append(pool.stage(title=item.get('topic', 'Hướng dẫn lâm sàng')[:180], content=content,
                                  source_url=url, domain='clinical', actor='seed_existing_source'))
    return list(dict.fromkeys(ids))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed-existing', action='store_true')
    args = parser.parse_args()
    pool = get_knowledge_pool()
    if args.seed_existing:
        ids = seed_candidates(pool)
        print(json.dumps({'staged_documents':len(ids),'approved_automatically':0,'status':'PENDING_INDEPENDENT_REVIEW'},ensure_ascii=False))
    else:
        print(json.dumps(pool.inventory(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
