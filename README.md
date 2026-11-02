## privacy-genie-doc

개인정보보호 관련 문서를 **RAG 검색에 활용할 수 있는 청크와 임베딩으로 가공하는 역할**로 법령뿐만
아니라 향후 지침, 가이드, 평가자료 등 다양한 개인정보보호 관련 문서를 처리하는 것을 목표로 합니다.
DB(저장·기록·마이그레이션)와 검색은 [privacy_genie_web](https://github.com/mady-21/privacy_genie_web)(Rails)이
관장합니다. doc은 청크와 벡터를 API로 내주고, 질문 벡터를 계산해 줍니다(아래 "역할 분담").

## 구조
- app/parsers: HWPX 추출과 법령 공통 구조 파싱
- app/chunkers/base_law_chunker.py: 텍스트 구성·조문 분할·메타데이터·JSON 저장
- app/chunkers/act_chunker.py: 법률 처리 정책(부칙과 제10장 벌칙 중 형사처벌 조문 제외, 과태료 조문은 포함)
- app/chunkers/decree_chunker.py: 시행령 처리 정책(부칙을 뺀 본문 조문 모두 포함)
- app/embeddings/embedding_text_builder.py: 임베딩 입력 텍스트 생성(개정이력 annotation 제거, 모델 중립)
- app/embeddings/embedder.py: 임베딩 모델을 한 번만 불러와 텍스트를 정규화된 벡터로 변환
- app/embeddings/store.py: 문서 벡터 파일 저장·불러오기(청크와 어긋났으면 거부)
- app/constants/embedding.py: 임베딩 모델 이름·벡터 차원·요청 제한
- app/documents/law_documents.py: 문서 종류별 원본·청커·기대 제목(`LAW_SOURCES`), web 적재용 응답 생성
- app/main.py: FastAPI 앱(`/health`, `/embeddings`, `/documents/{document_type}`)
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
- 부칙: 법률·시행령 모두 부칙 조문은 청크에서 뺍니다(2026-10-21 결정, 법률 4개·시행령 3개
  청크). 파싱 결과(`law_structure.json`)에는 남아 있습니다. 조문의 시행 여부는 본문의
  `[시행일: ...]` 표기로 판단하므로 지장이 없고, 잃는 건 전환기 질문(예: 시행령 부칙 제2조의
  기존 보호책임자 신고 유예)에 대한 근거입니다. 판단은 `BaseLawChunker.should_exclude`에서
  하고, 법률·시행령 청커가 이를 그대로 따릅니다.
- 법률: 제10장 벌칙 중 형사처벌 조문(제70~74조의2)만 제외하고, 과태료 조문(제75·76조)은
  포함합니다. 제외/포함 대상은 `ActChunker.EXCLUDED_ARTICLES` /
  `INCLUDED_PENALTY_ARTICLES`에 (조번호, 제목)으로 명시되어 있고, 벌칙 장에 두 목록
  어디에도 없는 조문이 나타나면(법 개정으로 조문이 추가·재배치된 경우) 조용히 넘어가지
  않고 `ValueError`로 실패합니다. 이 경우 두 목록을 갱신해야 합니다.
- 시행령: 본문 조문은 모두 포함합니다. 제63조(과태료의 부과기준)는 본문이 "별표 2와 같다"뿐이라
  과태료 대상·상한 질문까지만 답할 수 있습니다(금액 상세는 아래 "앞으로 할 일").

## 임베딩 텍스트
`EmbeddingTextBuilder`는 청크의 원문(`text`, 인용·출력용으로 그대로 보존)과는 별도로,
임베딩 모델에 넣을 입력 문자열을 만듭니다. 지금 모델(KURE-v1)은 프리픽스가 필요 없어서
특정 모델용 프리픽스는 붙이지 않습니다. 프리픽스가 필요한 모델로 바꾸면 그때 추가합니다.
- `<개정 ...>`, `<신설 ...>` 같은 앵글브래킷과 `[본조신설 ...]`, `[전문개정 ...]`,
  `[제목개정 ...]`, `[시행일: ...]`로 시작하는 스퀘어브래킷을 제거합니다. 다른
  스퀘어브래킷(예: 시행령의 `[법인의 경우에는 ...]`처럼 실질 내용을 담은 것)은 보존합니다.

## 임베딩 모델과 API
임베딩 모델은 `nlpai-lab/KURE-v1`(1024차원, 최대 8,192토큰, MIT)입니다. bge-m3를 한국어 검색
데이터로 추가 학습한 모델이고, 입력에 `query:`/`passage:` 같은 프리픽스가 필요 없습니다.
모델 이름과 차원은 `app/constants/embedding.py` 한 곳에 있고, 서버가 뜰 때 실제 모델 차원이
`EMBEDDING_DIMENSION`과 다르면 시작하지 않습니다. 모델을 바꾸면 문서 벡터를 전부 다시
만들어야 하기 때문입니다.

### 문서 벡터 파일
문서 청크를 임베딩하는 건 CPU에서 수 분이 걸려서(법률 약 6.5분, 시행령 약 3.7분), 요청 때마다
하지 않고 `rebuild_chunks.py`가 청크와 함께 `documents/processed/{act,decree}/embeddings.npz`로
저장합니다. 파일에는 벡터와 함께 청크 목록, 임베딩 입력 텍스트의 해시, 모델 이름이 들어 있어서
다음 경우에는 `GET /documents`가 503과 "rebuild를 다시 하라"는 메시지를 돌려줍니다.
- 파일이 없음
- 다른 모델로 만든 벡터
- `chunks.json`의 청크 목록이 바뀜(`--skip-embeddings`로 청크만 다시 만든 경우 등)
- `chunk_id`는 같은데 본문이나 정제 규칙이 바뀜(개정이력 표기만 바뀐 건 임베딩 입력에서 빠지므로 괜찮음)

### `GET /documents/{document_type}` — web 적재용
web(Rails)의 동기화 작업이 부르는 API입니다. `document_type`은 `act` 또는 `decree`이고, 그 외는
422입니다. 위 파일을 읽어서 문서 정보와 청크 전체를 벡터와 함께 돌려줍니다. 임베딩을 다시
계산하지 않아서 1초 안에 응답합니다(법률 156청크 3.6MB, 시행령 168청크 3.9MB). 부칙은 없습니다.

```json
{
  "source_key": "privacy",
  "document_type": "act",
  "name": "개인정보 보호법",
  "law_number": "법률 제21445호",
  "law_effective_date": "2026-09-11",
  "embedding_model": "nlpai-lab/KURE-v1",
  "embedding_dimension": 1024,
  "chunks": [
    {
      "chunk_id": "법률 제21445호:main:제1조:1",
      "position": 1,
      "article_number": "제1조",
      "article_title": "목적",
      "chapter": "제1장 총칙",
      "section": null,
      "text": "원문 그대로(인용·표시용)",
      "part_index": 1,
      "part_count": 1,
      "is_effective": true,
      "article_effective_date": null,
      "metadata": {},
      "embedding": [0.0123, "... 1024개"]
    }
  ]
}
```

- `source_key`는 원본 파일 이름(`privacy`, `privacy_decree`)이라 법이 개정돼도 같습니다.
- `chunk_id`는 같은 원문이면 항상 같은 값이라 web은 이걸 키로 upsert하고, 응답에 없는 청크는
  지우면 됩니다. `position`은 응답 안의 순서(1부터)입니다.
- `text`는 원문 그대로이고 `embedding`은 개정이력 표기를 걷어낸 텍스트로 계산한 값입니다.
- 미시행 조문도 `is_effective=false`와 `article_effective_date`를 붙여서 그대로 넣습니다.
  검색에서 거를지, "아직 시행 전"이라고 답할지는 web이 정합니다.

### `POST /embeddings` — 질문 벡터
web이 사용자 질문을 벡터로 바꿀 때 부릅니다. web은 이 벡터로 자기 DB(pgvector)에서 검색합니다.
문서 벡터와 같은 모델이라 바로 비교할 수 있고, 벡터는 길이 1로 정규화되어 있어서 내적이 곧
코사인 유사도입니다.

```bash
curl -X POST localhost:8000/embeddings -H 'Content-Type: application/json' \
  -d '{"texts": ["탈퇴한 회원의 정보는 언제 지워야 하나요?"]}'
# {"model": "nlpai-lab/KURE-v1", "dimension": 1024, "embeddings": [[0.0123, ...]]}
```

- 요청당 텍스트 64개, 텍스트당 10,000자까지입니다. 빈 목록·공백뿐인 텍스트·제한 초과는 422.
- 모델은 서버 시작 때 불러옵니다(CPU 기준 약 11초). 이후 질문 1개 인코딩은 약 0.6초입니다.
- 모델 가중치(약 2.3GB)는 Docker의 `embedding-models` 볼륨(`HF_HOME=/models/huggingface`)에
  캐시됩니다. compose에 `HF_HUB_OFFLINE=1`을 켜 두어서 서버는 캐시만 쓰고 Hugging Face
  서버에 접속하지 않습니다. 볼륨이 비어 있으면(새 환경, 모델 교체) 서버가 뜨지 않으므로,
  일회용 컨테이너로 먼저 한 번 받습니다.

```bash
docker compose run --rm -e HF_HUB_OFFLINE=0 doc python -c \
  "from sentence_transformers import SentenceTransformer; SentenceTransformer('nlpai-lab/KURE-v1')"
```

## 테스트로 검증하기
`save_preview`/`save_classification`은 수동 디버깅용 보조 파일이고, 청킹·임베딩 텍스트
로직의 실제 검증은 `tests/`의 unittest assertion으로 합니다. 합성 fixture로 분할 경계·
annotation 제거 규칙을 검증하고(`tests/test_pipeline.py`, `tests/test_embeddings.py`),
실제 hwpx 문서로 회귀를 가드합니다(`tests/test_documents.py`).

## 임베딩 모델 평가
KURE-v1은 평가 없이 정했습니다(한국어 특화, bge-m3와 같은 구조라 바꾸기 쉬움). 평가셋
`evaluation/retrieval_eval_v1.json`(30문항: 일반 23, 과태료 7)은 모델이나 청킹 기준을 바꿀지
고민될 때 비교하는 기준으로 둡니다.
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
docker exec -w /app privacy-genie-doc python evaluate_retrieval.py --model nlpai-lab/KURE-v1
docker exec -w /app privacy-genie-doc python evaluate_retrieval.py --model nlpai-lab/KURE-v1 --no-split
docker exec -w /app privacy-genie-doc python evaluate_retrieval.py --model nlpai-lab/KURE-v1 --output documents/processed/eval/kure-v1.json
```

## 앞으로 할 일
- 분할 기준 재검토: 1,000자 분할은 512토큰 모델에 맞춘 값이었고 KURE-v1은 8,192토큰을
  받습니다. 지금은 유지하고, 평가 스크립트(분할/비분할)나 질의 로그로 계속 쓸지 확인.
- 과태료 금액 상세: 제63조 본문은 "별표 2와 같다"만 있고 실제 금액은 HWPX 표(별표)에
  있는데, `HwpxParser`가 표를 버리고 있어 별도 표 파싱이 필요.
- 가이드·지침 문서 전용 청킹 전략.
- web 연동(web 레포):
  - 마이그레이션: pgvector 확장, `document_chunks`에 `chunk_id`(unique)·`part_index`·`part_count`·
    `is_effective`·`article_effective_date`·`embedding vector(1024)`, `documents`에 `embedding_model`.
  - 동기화 rake 작업: `GET /documents/{act,decree}` → 문서 단위 트랜잭션으로 `chunk_id` 기준 upsert,
    응답에 없는 청크 삭제. `embedding_model`이 저장된 값과 다르면 기존 벡터와 섞지 말고 전체 재적재.
  - 검색: `POST /embeddings`로 질문 벡터를 받아 pgvector로 가까운 청크 검색 → LLM 답변.
  - 부칙이 빠졌으므로 `document_supplements` 테이블을 어떻게 할지 결정.

## Docker 실행

```bash
docker exec -w /app privacy-genie-doc python rebuild_chunks.py --type act
docker exec -w /app privacy-genie-doc python rebuild_chunks.py --type decree
docker exec -w /app privacy-genie-doc python -m unittest discover -s tests -v
```

- `rebuild_chunks.py`는 청크와 문서 벡터를 같이 만듭니다(벡터 계산에 CPU로 수 분). 청크만
  빠르게 확인하려면 `--skip-embeddings`를 붙이되, 그 상태로는 벡터가 청크와 어긋나서
  `GET /documents`가 503을 돌려줍니다.
- `GET /documents`는 요청마다 파일을 읽으므로 rebuild 뒤에 서버를 재시작할 필요는 없습니다.
  rebuild 뒤에는 web의 동기화 작업을 다시 돌리면 됩니다.

## 역할 분담

| 일 | privacy-genie-doc (이 레포) | privacy_genie_web (Rails) |
|---|---|---|
| 원본 파싱·청킹, 문서 벡터 계산(rebuild, 파일 저장) | O | |
| 청크+벡터 제공 `GET /documents/{type}` | O | |
| 질문 벡터 계산 `POST /embeddings` | O | |
| 스키마·마이그레이션(pgvector, 벡터 컬럼), 저장·기록 | | O |
| 동기화 작업(doc API → DB), pgvector 검색, LLM 답변 | | O |

- DB의 모든 것(마이그레이션, 기록)은 Rails가 관장합니다. doc은 DB에 직접 쓰지 않고 API로
  데이터를 내주기만 합니다.
- 문서와 질문은 반드시 같은 모델로 임베딩해야 하므로 모델은 doc 한 곳에만 둡니다.

### 처리 흐름

문서 적재(원문이 바뀔 때):

```text
[doc] rebuild_chunks.py: 원본 Parsing → 구조 분석 → Chunking → 청크 Embedding → chunks.json + embeddings.npz
[web] 동기화 작업 ──GET /documents/{act,decree}──▶ [doc] 파일을 읽어 청크+벡터 응답
[web] chunk_id 기준으로 DB(pgvector)에 저장
```

사용자 질문:

```text
[web] 사용자 질문 ──POST /embeddings──▶ [doc] 질문 벡터
[web] pgvector로 가까운 청크 검색 → LLM 답변
```
