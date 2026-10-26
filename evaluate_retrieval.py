"임베딩 모델 하나로 검색 평가셋을 돌려 Recall@k·MRR·현행 적중률을 출력한다."
import argparse
import json
from pathlib import Path

from app.chunkers.base_law_chunker import BaseLawChunker
from app.constants.paths import RETRIEVAL_EVAL_PATH, TEXT_ENCODING
from app.embeddings.embedding_text_builder import EmbeddingTextBuilder
from app.evaluation.retrieval import build_law_chunks, evaluate, hit_at_k, load_eval_set, rank_chunks, summarize


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--model', required=True, help='Hugging Face 모델 이름 (예: nlpai-lab/KURE-v1)')
    split = cli.add_mutually_exclusive_group()
    split.add_argument('--max-chunk-chars', type=int, help='청크 분할 기준 글자 수 (기본: BaseLawChunker.MAX_CHUNK_CHARS)')
    split.add_argument('--no-split', action='store_true', help='긴 조문도 분할하지 않음')
    cli.add_argument('--top-k', type=int, help='기본: 평가셋의 top_k')
    cli.add_argument('--eval-set', type=Path, default=RETRIEVAL_EVAL_PATH)
    cli.add_argument('--output', type=Path, help='요약과 문항별 결과를 JSON으로 저장할 경로')
    args = cli.parse_args()

    from sentence_transformers import SentenceTransformer

    eval_set = load_eval_set(args.eval_set)
    questions = eval_set['questions']
    top_k = args.top_k or eval_set['top_k']
    max_chunk_chars = float('inf') if args.no_split else args.max_chunk_chars
    chunks = build_law_chunks(max_chunk_chars)
    builder = EmbeddingTextBuilder()
    passages = [builder.build(document_name=chunk['law_name'], chunk=chunk) for chunk in chunks]

    model = SentenceTransformer(args.model, device='cpu')
    truncated = sum(1 for text in passages if len(model.tokenizer(text)['input_ids']) > model.max_seq_length)
    options = {'normalize_embeddings': True, 'convert_to_numpy': True, 'show_progress_bar': False}
    passage_vectors = model.encode(passages, **options)
    query_vectors = model.encode([q['question'] for q in questions], **options)

    results = evaluate(questions, chunks, rank_chunks(query_vectors, passage_vectors))
    summary = summarize(results, top_k)

    condition = '분할 안 함' if args.no_split else f'{max_chunk_chars or BaseLawChunker.MAX_CHUNK_CHARS}자 기준 분할'
    print(f'모델: {args.model}')
    print(f'청킹: {condition}, 청크 {len(chunks)}개 (max_seq_length {model.max_seq_length} 초과 {truncated}개)')
    for name in ('overall', 'general', 'fine'):
        stats = summary[name]
        print(f"{name:8} Recall@{top_k} {stats['recall']:.3f}  MRR {stats['mrr']:.3f}  ({stats['count']}문항)")
    if 'effective_hit' in summary:
        stats = summary['effective_hit']
        print(f"현행 적중률@{top_k} {stats['recall']:.3f}  ({stats['count']}문항)")
    misses = [
        r for r in results
        if not hit_at_k(r['rank'], top_k) or ('effective_rank' in r and not hit_at_k(r['effective_rank'], top_k))
    ]
    if misses:
        print('놓친 문항:')
        for result in misses:
            print(f"  {result['id']}: 순위 {result['rank']}, 현행 순위 {result.get('effective_rank', '-')}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {'model': args.model, 'condition': condition, 'top_k': top_k, 'summary': summary, 'results': results}
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding=TEXT_ENCODING)


if __name__ == '__main__':
    main()
