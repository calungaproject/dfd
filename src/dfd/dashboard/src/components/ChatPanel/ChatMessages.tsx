import { useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ChatMessage } from '../../api/types';
import ToolActivity from './ToolActivity';

interface ToolCallState {
  name: string;
  input?: Record<string, unknown>;
  active: boolean;
}

interface ChatMessagesProps {
  messages: ChatMessage[];
  streamingText: string;
  isStreaming: boolean;
  isThinking: boolean;
  toolCalls: ToolCallState[];
  error: string | null;
}

interface PersistedToolCall {
  name: string;
  input?: Record<string, unknown>;
}

export default function ChatMessages({
  messages,
  streamingText,
  isStreaming,
  isThinking,
  toolCalls,
  error,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, toolCalls, isThinking]);

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
      {messages.map((msg) => (
        <div key={msg.id}>
          {msg.role === 'assistant' && Array.isArray(msg.tool_calls) &&
            (msg.tool_calls as PersistedToolCall[]).map((tc, i) => (
              <ToolActivity key={`${msg.id}-tc-${i}`} name={tc.name} input={tc.input} active={false} />
            ))}
          {msg.content ? (
            <div
              style={{
                marginBottom: '0.75rem',
                padding: '0.5rem 0.75rem',
                borderRadius: '8px',
                ...(msg.role === 'user'
                  ? {
                      background: 'var(--pf-t--global--color--brand--default)',
                      color: '#fff',
                      marginLeft: '4rem',
                      textAlign: 'right' as const,
                    }
                  : {
                      background: 'var(--pf-t--global--background--color--secondary--default)',
                      marginRight: '2rem',
                    }),
              }}
            >
              {msg.role === 'assistant' ? (
                <div className="chat-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
              )}
            </div>
          ) : null}
        </div>
      ))}

      {toolCalls.map((tc, i) => (
        <ToolActivity key={`${tc.name}-${i}`} name={tc.name} input={tc.input} active={tc.active} />
      ))}

      {isThinking && (
        <div style={{
          padding: '0.5rem 0.75rem',
          fontStyle: 'italic',
          color: 'var(--pf-t--global--text--color--subtle)',
        }}>
          Thinking...
        </div>
      )}

      {isStreaming && streamingText && (
        <div style={{
          marginBottom: '0.75rem',
          padding: '0.5rem 0.75rem',
          borderRadius: '8px',
          background: 'var(--pf-t--global--background--color--secondary--default)',
          marginRight: '2rem',
        }}>
          <div className="chat-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingText}</ReactMarkdown>
          </div>
        </div>
      )}

      {error && (
        <div style={{
          padding: '0.5rem 0.75rem',
          color: 'var(--pf-t--global--color--status--danger--default)',
          fontStyle: 'italic',
        }}>
          Error: {error}
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
