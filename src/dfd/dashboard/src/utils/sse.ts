import type { SSEEvent } from '../api/types';

export async function* parseSSEStream(
  response: Response,
): AsyncGenerator<SSEEvent> {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith(':')) continue;
      if (trimmed.startsWith('data: ')) {
        try {
          yield JSON.parse(trimmed.slice(6)) as SSEEvent;
        } catch {
          // skip malformed JSON
        }
      }
    }
  }
}
