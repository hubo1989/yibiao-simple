/**
 * Server-Sent Events (SSE) 解析工具函数
 */

export interface ParsedSSEEvent {
  [key: string]: unknown;
}

export interface SSEParseResult {
  remainder: string;
  done: boolean;
}

/**
 * 解析 SSE 流数据
 * @param buffer - 累积的缓冲区字符串
 * @param onEvent - 事件回调函数
 * @returns 解析结果，包含剩余缓冲区和是否完成标志
 */
export function consumeSseEvents(
  buffer: string,
  onEvent: (payload: ParsedSSEEvent) => void
): SSEParseResult {
  const normalizedBuffer = buffer.replace(/\r\n/g, '\n');
  const events = normalizedBuffer.split('\n\n');
  const remainder = events.pop() ?? '';

  for (const event of events) {
    if (!event.trim()) {
      continue;
    }

    const data = event
      .split('\n')
      .filter((line) => line.startsWith('data: '))
      .map((line) => line.slice(6))
      .join('\n')
      .trim();

    if (!data) {
      continue;
    }

    if (data === '[DONE]') {
      return { remainder: '', done: true };
    }

    try {
      onEvent(JSON.parse(data));
    } catch {
      // Ignore malformed complete SSE events but keep the stream alive.
    }
  }

  return { remainder, done: false };
}

/**
 * 解析 SSE 数据行（简化版本，用于单行解析）
 * @param line - SSE 数据行
 * @returns 解析后的对象或 null
 */
export function parseSSELine(line: string): ParsedSSEEvent | null {
  if (!line.startsWith('data: ')) {
    return null;
  }

  const data = line.slice(6).trim();

  if (data === '[DONE]') {
    return { done: true } as ParsedSSEEvent;
  }

  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}
