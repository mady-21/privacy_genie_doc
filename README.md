## privacy-genie-doc

개인정보보호 관련 문서를 **RAG 검색에 활용할 수 있는 데이터로 변환하고 검색하는 역할**로
법령뿐만 아니라 향후 지침, 가이드, 평가자료 등 다양한 개인정보보호 관련 문서를 처리하는 것을 목표로 합니다.

## 구조
- app/parsers: HWPX 추출과 법령 공통 구조 파싱
- app/chunkers/base_law_chunker.py: 텍스트 구성·조문 분할·메타데이터·JSON 저장
- app/chunkers/act_chunker.py: 법률 처리 정책(제10장 벌칙 제외)
- app/chunkers/decree_chunker.py: 시행령 처리 정책(제63조 과태료 제외)
- app/embeddings/embedding_text_builder.py: 임베딩 모델 입력 텍스트 생성(passage 프리픽스, 개정이력 annotation 제거)
- documents/source/laws: privacy.hwpx, privacy_decree.hwpx
- documents/source/guides: 가이드 원문 보관(전용 청커는 아직 미구현)
- documents/processed/act, decree: 문서별 처리 결과

## 청킹 전략
기본 단위는 조(article) 하나당 청크 하나입니다. 다만 조문이 길면(기본 1000자 초과,
`BaseLawChunker.MAX_CHUNK_CHARS`) 항(①②③...)이 있으면 항 경계에서, 없으면
호(1. 2. 3...) 경계에서 분할합니다. 목(가.나.다...)은 항상 상위 항/호에 붙어 분할
경계가 되지 않고, 항/호 하나가 제한보다 길어도 문장 중간을 끊지 않습니다.

분할된 청크는 법명·장·절·조문 heading을 매번 반복해서 포함합니다(검색 시 단독으로
의미가 통해야 하기 때문에 의도된 중복입니다). `chunk_id`에는 분할된 경우에만
`:part{N}` suffix가 붙고, 모든 청크에 `part_index`/`part_count` 필드가 있습니다.

## 임베딩 텍스트
`EmbeddingTextBuilder`는 청크의 원문(`text`, 인용·출력용으로 그대로 보존)과는 별도로,
임베딩 모델에 넣을 입력 문자열을 만듭니다.
- `intfloat/multilingual-e5-small` 등 e5 계열 모델 규격에 맞춰 `passage: ` 프리픽스를 붙입니다.
- `<개정 ...>`, `<신설 ...>` 같은 앵글브래킷과 `[본조신설 ...]`, `[전문개정 ...]`,
  `[제목개정 ...]`, `[시행일: ...]`로 시작하는 스퀘어브래킷을 제거합니다. 다른
  스퀘어브래킷(예: 시행령의 `[법인의 경우에는 ...]`처럼 실질 내용을 담은 것)은 보존합니다.

## 테스트로 검증하기
`save_preview`/`save_classification`은 수동 디버깅용 보조 파일이고, 청킹·임베딩 텍스트
로직의 실제 검증은 `tests/`의 unittest assertion으로 합니다. 합성 fixture로 분할 경계·
annotation 제거 규칙을 검증하고(`tests/test_pipeline.py`, `tests/test_embeddings.py`),
실제 hwpx 문서로 회귀를 가드합니다(`tests/test_documents.py`).

## Docker 실행

```bash
docker exec -w /app privacy-genie-doc python rebuild_chunks.py --type act
docker exec -w /app privacy-genie-doc python rebuild_chunks.py --type decree
docker exec -w /app privacy-genie-doc python -m unittest discover -s tests -v
```


### 처리 흐름

```text
개인정보보호 관련 문서
        │
        ▼
문서 Parsing
        │
        ▼
문서 구조 분석
        │
        ▼
Chunking
        │
        ▼
Embedding
        │
        ▼
Vector DB 저장
```

사용자 질문에 대한 검색 요청이 들어오면 다음 과정을 수행합니다.

```text
Rails 검색 요청
        │
        ▼
질문 Embedding
        │
        ▼
Vector Search
        │
        ▼
관련 Chunk 검색
        │
        ▼
Rails로 검색 결과 반환
```

즉, **개인정보보호 관련 문서를 AI 검색에 적합한 형태로 가공하고, 사용자 질문과 관련된 문서를 찾아 반환하는 역할**을 담당합니다.

LLM을 이용한 최종 답변 생성 및 사용자 요청 처리는 별도의 Rails 애플리케이션인 [privacy_genie_web](https://github.com/mady-21/privacy_genie_web)에서 담당합니다.

