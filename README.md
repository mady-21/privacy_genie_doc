## privacy-genie-doc

개인정보보호 관련 문서를 **RAG 검색에 활용할 수 있는 데이터로 변환하고 검색하는 역할**로
법령뿐만 아니라 향후 지침, 가이드, 평가자료 등 다양한 개인정보보호 관련 문서를 처리하는 것을 목표로 합니다.

## 구조
- app/parsers: HWPX 추출과 법령 공통 구조 파싱
- app/chunkers/base_law_chunker.py: 텍스트 구성·조문 분할·메타데이터·JSON 저장
- app/chunkers/act_chunker.py: 법률 처리 정책(제10장 벌칙 중 형사처벌 조문만 제외, 과태료 조문은 포함)
- app/chunkers/decree_chunker.py: 시행령 처리 정책(모든 조문 포함)
- app/embeddings/embedding_text_builder.py: 임베딩 입력 텍스트 생성(개정이력 annotation 제거, 모델 중립)
- app/evaluation/retrieval.py: 검색 평가 로직(정답 판정, Recall@k·MRR·현행 적중률)
- evaluation/retrieval_eval_v1.json: 검색 평가셋 v1(30문항)
- evaluate_retrieval.py: 임베딩 모델 하나로 평가셋을 돌리는 스크립트
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

## 시행일 메타데이터
법령 원문에는 현재 시행 중인 조문과, 아직 시행되지 않은 개정 미리보기(`[시행일:
YYYY. M. D.] ...`로 표시)가 같은 조번호로 섞여 있습니다(예: 제2조가 현행/미시행
두 occurrence로 나뉘어 각각 청크가 됨). 이를 구분하기 위해 모든 청크에
`is_effective`(기본 `true`)와 `article_effective_date`(기본 `null`)를 항상 포함합니다.
`[시행일: ...]` 표기가 붙은 occurrence만 `is_effective=false`,
`article_effective_date`에 ISO 날짜가 채워집니다.

판단 기준은 실행 시점(wall-clock)이 아니라 **원문에 표기가 있는지 여부**입니다. 그래서
같은 hwpx로 언제 다시 빌드해도 같은 결과가 나옵니다. 법령 전체의 `law_effective_date`,
부칙의 `promulgation_date`도 모두 ISO(`YYYY-MM-DD`) 형식으로 통일되어 있습니다.

예를 들어 제75조(과태료)는 occurrence 1(현행)은 `is_effective=true`, occurrence 2
(제2항제15호가 2027-07-01부터 적용)는 `is_effective=false`로 나뉘어 청크화됩니다.

## 제외 정책
- 법률: 제10장 벌칙 중 형사처벌 조문(제70~74조의2)만 제외하고, 과태료 조문(제75·76조)은
  포함합니다. 제외/포함 대상은 `ActChunker.EXCLUDED_ARTICLES` /
  `INCLUDED_PENALTY_ARTICLES`에 (조번호, 제목)으로 명시되어 있고, 벌칙 장에 두 목록
  어디에도 없는 조문이 나타나면(법 개정으로 조문이 추가·재배치된 경우) 조용히 넘어가지
  않고 `ValueError`로 실패합니다. 이 경우 두 목록을 갱신해야 합니다.
- 시행령: 모든 조문을 포함합니다. 제63조(과태료의 부과기준)는 본문이 "별표 2와 같다"뿐이라
  과태료 대상·상한 질문까지만 답할 수 있습니다(금액 상세는 아래 "앞으로 할 일").

## 임베딩 텍스트
`EmbeddingTextBuilder`는 청크의 원문(`text`, 인용·출력용으로 그대로 보존)과는 별도로,
임베딩 모델에 넣을 입력 문자열을 만듭니다. 임베딩 모델은 아직 정하지 않았으므로 특정
모델용 프리픽스(예: e5의 `query:`/`passage:`)는 붙이지 않습니다. 모델별 입력 규칙은
모델을 정한 뒤에 추가합니다.
- `<개정 ...>`, `<신설 ...>` 같은 앵글브래킷과 `[본조신설 ...]`, `[전문개정 ...]`,
  `[제목개정 ...]`, `[시행일: ...]`로 시작하는 스퀘어브래킷을 제거합니다. 다른
  스퀘어브래킷(예: 시행령의 `[법인의 경우에는 ...]`처럼 실질 내용을 담은 것)은 보존합니다.

## 테스트로 검증하기
`save_preview`/`save_classification`은 수동 디버깅용 보조 파일이고, 청킹·임베딩 텍스트
로직의 실제 검증은 `tests/`의 unittest assertion으로 합니다. 합성 fixture로 분할 경계·
annotation 제거 규칙을 검증하고(`tests/test_pipeline.py`, `tests/test_embeddings.py`),
실제 hwpx 문서로 회귀를 가드합니다(`tests/test_documents.py`).

## 임베딩 모델 평가
모델은 `evaluation/retrieval_eval_v1.json`(30문항: 일반 23, 과태료 7)으로 비교해서 고릅니다.
- 적중 판정: 검색된 청크의 문서 종류·조번호가 정답 조문과 같으면 적중입니다(본문 조문만,
  occurrence·part는 무시). 정답이 여러 조문이면 하나만 맞아도 적중입니다.
- 주 지표: Recall@5(상위 5개 안에 정답이 있는 비율), MRR(정답 순위의 역수 평균).
- 보조 지표: 현행본이 있는 문항(F1~F7, G11, G22)은 상위 5개에 `is_effective=true` 청크가
  있어야 적중으로 보는 "현행 적중률"을 따로 셉니다. G15(미시행 조문뿐)에서 "현행이 아님"을
  답하는지는 web 답변 평가에서 봅니다.
- 30문항이라 한 문항이 Recall@5로 3.3%p입니다. 1~2문항 차이는 잡음으로 봅니다.
- `tests/test_retrieval_eval.py`가 정답 조문이 실제 청크에 있는지 확인하므로, 법 개정으로
  조문 번호가 바뀌면 테스트가 깨집니다. 그때 평가셋을 고칩니다.

분할 기준을 바꿔 가며 돌릴 수 있습니다(1,000자 기준은 512토큰 모델에 맞춘 값이라, 긴
입력을 받는 모델은 분할하지 않은 조건과 같이 비교합니다).

```bash
docker exec -w /app privacy-genie-doc python evaluate_retrieval.py --model BAAI/bge-m3
docker exec -w /app privacy-genie-doc python evaluate_retrieval.py --model BAAI/bge-m3 --no-split
docker exec -w /app privacy-genie-doc python evaluate_retrieval.py --model BAAI/bge-m3 --output documents/processed/eval/bge-m3.json
```

## 앞으로 할 일
- 임베딩 모델 결정: 후보 모델 다운로드 → 분할/비분할 조건으로 측정 → ADR 작성 → 결정 반영
  (모델별 입력 규칙, 분할 기준, 벡터 차원). 평가셋 문서가 베이스라인으로 둔 e5-small을 다시
  후보로 쓴다면 `query:`/`passage:` 프리픽스 처리를 그때 추가해야 공정합니다.
- 과태료 금액 상세: 제63조 본문은 "별표 2와 같다"만 있고 실제 금액은 HWPX 표(별표)에
  있는데, `HwpxParser`가 표를 버리고 있어 별도 표 파싱이 필요.
- 가이드·지침 문서 전용 청킹 전략.
- 벡터 저장소(모델이 정해져야 벡터 차원이 정해짐)·검색 API 연동.

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

