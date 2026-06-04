import { useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createChatSession,
  fetchChatSessions,
  fetchChatMessages,
  sendChatMessage,
} from '../api/client';
import { parseSSEStream } from '../utils/sse';
import type { ChatMessage, SSEEvent } from '../api/types';

interface ToolCallState {
  name: string;
  input?: Record<string, unknown>;
  result?: string;
  active: boolean;
}

interface StreamState {
  isStreaming: boolean;
  isThinking: boolean;
  streamingText: string;
  toolCalls: ToolCallState[];
  error: string | null;
}

export function useChatSessions(limit = 20) {
  return useQuery({
    queryKey: ['chatSessions', limit],
    queryFn: () => fetchChatSessions(limit),
  });
}

export function useChatMessages(sessionId: string | null) {
  return useQuery({
    queryKey: ['chatMessages', sessionId],
    queryFn: () => fetchChatMessages(sessionId!),
    enabled: !!sessionId,
  });
}

export function useChat() {
  const qc = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stream, setStream] = useState<StreamState>({
    isStreaming: false,
    isThinking: false,
    streamingText: '',
    toolCalls: [],
    error: null,
  });

  const startSession = useCallback(async (contextRunId?: string, firstMessage?: string) => {
    const title = contextRunId
      ? `Run: ${contextRunId}`
      : firstMessage
        ? firstMessage.slice(0, 80) + (firstMessage.length > 80 ? '...' : '')
        : 'New chat';
    const { session_id } = await createChatSession({
      title,
      context_pipeline_run_id: contextRunId,
    });
    setSessionId(session_id);
    qc.invalidateQueries({ queryKey: ['chatSessions'] });
    return session_id;
  }, [qc]);

  const handleSSEEvent = useCallback(
    (event: SSEEvent, currentText: string, setText: (t: string) => void) => {
      switch (event.type) {
        case 'tool_call':
          setStream((prev) => ({
            ...prev,
            isThinking: false,
            toolCalls: [
              ...prev.toolCalls.map((tc) => ({ ...tc, active: false })),
              { name: event.name ?? '', input: event.input, active: true },
            ],
          }));
          break;

        case 'tool_result':
          setStream((prev) => ({
            ...prev,
            toolCalls: prev.toolCalls.map((tc) =>
              tc.name === event.name && tc.active
                ? { ...tc, result: event.result, active: false }
                : tc,
            ),
          }));
          break;

        case 'text_delta': {
          const newText = currentText + (event.text ?? '');
          setText(newText);
          setStream((prev) => ({
            ...prev,
            isThinking: false,
            streamingText: newText,
          }));
          break;
        }

        case 'done':
          break;

        case 'error':
          setStream((prev) => ({
            ...prev,
            isStreaming: false,
            isThinking: false,
            error: event.message ?? 'Unknown error',
          }));
          break;
      }
    },
    [],
  );

  const send = useCallback(async (message: string) => {
    let sid = sessionId;
    if (!sid) {
      sid = await startSession(undefined, message);
    }

    setStream({
      isStreaming: true,
      isThinking: true,
      streamingText: '',
      toolCalls: [],
      error: null,
    });

    qc.setQueryData(
      ['chatMessages', sid],
      (old: { messages: ChatMessage[] } | undefined) => ({
        messages: [
          ...(old?.messages ?? []),
          {
            id: Date.now(),
            session_id: sid!,
            role: 'user' as const,
            content: message,
            tool_calls: null,
            cost_usd: null,
            tokens_used: null,
            created_at: new Date().toISOString(),
          },
        ],
      }),
    );

    try {
      const response = await sendChatMessage(sid, message);
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }

      let currentSegmentText = '';
      let currentSegmentToolCalls: { name: string; input?: Record<string, unknown> }[] = [];
      let hasUnflushedToolCalls = false;
      let done = false;

      const flushSegment = (content: string, toolCalls: { name: string; input?: Record<string, unknown> }[]) => {
        if (!content && toolCalls.length === 0) return;
        const segmentContent = content;
        const segmentTools = toolCalls.length > 0 ? [...toolCalls] : null;
        qc.setQueryData(
          ['chatMessages', sid],
          (old: { messages: ChatMessage[] } | undefined) => ({
            messages: [
              ...(old?.messages ?? []),
              {
                id: Date.now() + Math.random(),
                session_id: sid!,
                role: 'assistant' as const,
                content: segmentContent,
                tool_calls: segmentTools,
                cost_usd: null,
                tokens_used: null,
                created_at: new Date().toISOString(),
              },
            ],
          }),
        );
      };

      for await (const event of parseSSEStream(response)) {
        if (event.type === 'tool_call') {
          if (currentSegmentText) {
            flushSegment(currentSegmentText, []);
            currentSegmentText = '';
            setStream((prev) => ({ ...prev, streamingText: '' }));
          }
          currentSegmentToolCalls.push({ name: event.name ?? '', input: event.input });
          hasUnflushedToolCalls = true;
        }

        if (event.type === 'text_delta' && hasUnflushedToolCalls) {
          flushSegment('', currentSegmentToolCalls);
          currentSegmentToolCalls = [];
          hasUnflushedToolCalls = false;
          setStream((prev) => ({ ...prev, toolCalls: [] }));
        }

        handleSSEEvent(event, currentSegmentText, (text) => {
          currentSegmentText = text;
        });

        if (event.type === 'done') {
          const finalContent = currentSegmentText || event.content || '';
          flushSegment(finalContent, currentSegmentToolCalls);
          done = true;
        }
      }

      if (done) {
        setStream({
          isStreaming: false,
          isThinking: false,
          streamingText: '',
          toolCalls: [],
          error: null,
        });
        if (!sessionId) {
          setTimeout(() => qc.invalidateQueries({ queryKey: ['chatSessions'] }), 3000);
        }
      }
    } catch (e) {
      setStream((prev) => ({
        ...prev,
        isStreaming: false,
        isThinking: false,
        error: e instanceof Error ? e.message : 'Unknown error',
      }));
      qc.invalidateQueries({ queryKey: ['chatMessages', sid] });
    }
  }, [sessionId, startSession, qc, handleSSEEvent]);

  return {
    sessionId,
    setSessionId,
    stream,
    send,
    startSession,
  };
}
