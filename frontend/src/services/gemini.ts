const API_URL = 'http://localhost:8000';

interface QueryResponse {
  answer: string;
  sources: Array<{
    company: string;
    title: string;
    relevance_score: number | null;
  }>;
  processing_time: number;
}

export async function sendMessage(message: string): Promise<string> {
  const res = await fetch(`${API_URL}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: message, top_k: 5, use_reranker: true }),
  });

  if (!res.ok) {
    throw new Error(`Server error: ${res.status}`);
  }

  const data: QueryResponse = await res.json();

  let result = data.answer;

  if (data.sources && data.sources.length > 0) {
    result += '\n\n---\n**참조 문서**\n';
    data.sources.forEach((s) => {
      const score = s.relevance_score ? ` (관련도: ${s.relevance_score})` : '';
      result += `- ${s.company} - ${s.title}${score}\n`;
    });
  }

  return result;
}
