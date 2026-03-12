import re
from typing import Literal

from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
)
from langchain_core.documents import Document

from app.core.config import settings

# semantic 전략에서 사용하는 섹션 키워드 → metadata section 매핑
# 긴 키워드를 먼저 배치하여 짧은 키워드와의 중복 매칭 방지
SECTION_PATTERNS: list[tuple[str, str]] = [
    ("주요업무", "main_tasks"),
    ("자격요건", "requirements"),
    ("필수 요구사항", "requirements"),
    ("우대사항", "preferred"),
    ("기술스택", "tech_stack"),
    ("기술 스택", "tech_stack"),
    ("상세설명", "description"),
    ("회사소개", "company_info"),
    ("직무", "title"),
    ("경력", "experience"),
    ("근무지", "location"),
    ("고용형태", "job_type"),
    ("복리후생", "benefits"),
    ("회사", "company_info"),
]


class JobChunker:
    """채용 공고 문서를 다양한 전략으로 청킹합니다."""

    def __init__(
        self,
        strategy: Literal["recursive", "semantic", "fixed"] = "recursive",
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.strategy = strategy
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    def chunk(self, documents: list[Document]) -> list[Document]:
        """선택된 전략에 따라 문서를 청킹합니다."""
        if self.strategy == "recursive":
            return self._recursive(documents)
        elif self.strategy == "semantic":
            return self._semantic(documents)
        elif self.strategy == "fixed":
            return self._fixed(documents)
        else:
            raise ValueError(f"지원하지 않는 전략: {self.strategy}")

    # ── recursive 전략 ──
    def _recursive(self, documents: list[Document]) -> list[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " "],
        )
        return splitter.split_documents(documents)

    # ── semantic 전략 ──
    def _semantic(self, documents: list[Document]) -> list[Document]:
        chunks: list[Document] = []
        sub_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n", ". ", " "],
        )

        for doc in documents:
            # 컨텍스트 prefix: 검색 시 어떤 회사/직무인지 알 수 있도록
            company = doc.metadata.get("company", "")
            title = doc.metadata.get("title", "")
            context_prefix = f"[{company} - {title}] " if company and title else ""

            sections = self._split_into_sections(doc.page_content)
            for section_name, section_text in sections:
                prefixed_text = context_prefix + section_text
                base_metadata = {**doc.metadata, "section": section_name}

                if len(prefixed_text) <= self.chunk_size:
                    chunks.append(Document(
                        page_content=prefixed_text,
                        metadata=base_metadata,
                    ))
                else:
                    sub_doc = Document(page_content=prefixed_text, metadata=base_metadata)
                    sub_chunks = sub_splitter.split_documents([sub_doc])
                    chunks.extend(sub_chunks)

        return chunks

    def _split_into_sections(self, text: str) -> list[tuple[str, str]]:
        """텍스트를 섹션 키워드 기준으로 분할합니다."""
        boundaries: list[tuple[int, str]] = []
        matched_positions: set[int] = set()

        for keyword, section_id in SECTION_PATTERNS:
            pattern = rf"^{re.escape(keyword)}[:：]"
            for match in re.finditer(pattern, text, re.MULTILINE):
                # 같은 위치에서 이미 더 긴 키워드가 매칭된 경우 스킵
                if match.start() in matched_positions:
                    continue
                boundaries.append((match.start(), section_id))
                matched_positions.add(match.start())

        if not boundaries:
            return [("full", text)]

        boundaries.sort(key=lambda x: x[0])

        sections: list[tuple[str, str]] = []

        # 첫 번째 boundary 이전 텍스트 처리
        if boundaries[0][0] > 0:
            preamble = text[:boundaries[0][0]].strip()
            if preamble:
                sections.append(("preamble", preamble))

        for i, (start, section_id) in enumerate(boundaries):
            end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
            section_text = text[start:end].strip()
            if section_text:
                sections.append((section_id, section_text))

        return sections

    # ── fixed 전략 ──
    def _fixed(self, documents: list[Document]) -> list[Document]:
        splitter = CharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separator="\n",
        )
        return splitter.split_documents(documents)


if __name__ == "__main__":
    from app.ingestion.loader import JobLoader

    loader = JobLoader()
    docs = loader.to_documents()

    for strategy in ["recursive", "semantic", "fixed"]:
        chunker = JobChunker(strategy=strategy, chunk_size=500)
        chunks = chunker.chunk(docs)
        print(f"[{strategy}] 청크 수: {len(chunks)}")
        if chunks:
            sample = chunks[0]
            print(f"  첫 청크 ({len(sample.page_content)}자): {sample.page_content[:80]}...")
            print(f"  metadata: {sample.metadata}")
        print()
