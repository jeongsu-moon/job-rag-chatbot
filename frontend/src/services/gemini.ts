const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export async function sendMessageStream(
  message: string,
  history: ChatMessage[],
  onToken: (token: string) => void,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question: message,
      top_k: 7,
      use_reranker: true,
      full_scan: true,
      history,
    }),
  });

  if (!res.ok) {
    throw new Error(`Server error: ${res.status}`);
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6);
      if (data === '[DONE]') return;
      try {
        const parsed = JSON.parse(data);
        if (parsed.token) onToken(parsed.token);
      } catch {
        // 파싱 실패한 라인 무시
      }
    }
  }
}
