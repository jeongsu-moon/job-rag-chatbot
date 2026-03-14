import json
from langchain_core.documents import Document


class JobLoader:
    """JSON 파일에서 채용 공고를 로드하여 LangChain Document로 변환합니다."""

    def __init__(self, file_path: str = "data/sample_jobs.json"):
        self.file_path = file_path
        self.raw_data: list[dict] = []
        self.documents: list[Document] = []

    def load_json(self) -> list[dict]:
        """JSON 파일에서 원시 데이터를 로드합니다."""
        with open(self.file_path, "r", encoding="utf-8") as f:
            self.raw_data = json.load(f)
        return self.raw_data

    @staticmethod
    def _to_str(value) -> str:
        """리스트 또는 문자열을 그대로 문자열로 변환합니다."""
        if isinstance(value, list):
            return "\n".join(f"  - {v}" for v in value)
        return str(value) if value else ""

    def _format_content(self, item: dict) -> str:
        """채용 공고 데이터를 하나의 포맷팅된 문자열로 변환합니다."""
        main_tasks = self._to_str(item.get("main_tasks", ""))
        requirements = self._to_str(item.get("requirements", ""))
        preferred = self._to_str(item.get("preferred", ""))
        tech_stack = ", ".join(item.get("tech_stack", []) if isinstance(item.get("tech_stack"), list) else [])

        return (
            f"회사: {item.get('company', '')}\n"
            f"직무: {item.get('title', '')}\n"
            f"경력: {item.get('experience', '')}\n"
            f"근무지: {item.get('location', '')}\n"
            f"고용형태: {item.get('job_type', '')}\n"
            f"기술스택: {tech_stack}\n"
            f"주요업무:\n{main_tasks}\n"
            f"자격요건:\n{requirements}\n"
            f"우대사항:\n{preferred}\n"
            f"상세설명: {item.get('description', '')}"
        )

    def to_documents(self) -> list[Document]:
        """로드된 데이터를 LangChain Document 리스트로 변환합니다."""
        if not self.raw_data:
            self.load_json()

        self.documents = []
        for item in self.raw_data:
            doc = Document(
                page_content=self._format_content(item),
                metadata={
                    "company": item.get("company", ""),
                    "title": item.get("title", ""),
                    "tech_stack": item.get("tech_stack", []),
                    "experience": item.get("experience", ""),
                    "location": item.get("location", ""),
                },
            )
            self.documents.append(doc)
        return self.documents


if __name__ == "__main__":
    loader = JobLoader()
    docs = loader.to_documents()
    print(f"총 {len(docs)}개의 Document 생성됨\n")
    print("=== 첫 번째 Document ===")
    print(f"[metadata] {docs[0].metadata}")
    print(f"[content]\n{docs[0].page_content[:500]}")
