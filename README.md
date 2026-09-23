## privacy-genie-doc

개인정보보호 관련 문서를 **RAG 검색에 활용할 수 있는 데이터로 변환하고 검색하는 역할**로
법령뿐만 아니라 향후 지침, 가이드, 평가자료 등 다양한 개인정보보호 관련 문서를 처리하는 것을 목표로 합니다.

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

