import { useEffect, useCallback, useRef, useState } from 'react';
import {
  Title,
  Button,
  Flex,
  FlexItem,
  FormSelect,
  FormSelectOption,
  Divider,
} from '@patternfly/react-core';
import { TimesIcon } from '@patternfly/react-icons';
import { useChat, useChatSessions, useChatMessages } from '../../hooks/useChat';
import ChatMessages from './ChatMessages';
import ChatInput from './ChatInput';
import './ChatPanel.css';

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  contextRunId?: string;
  onClearContext: () => void;
}

export default function ChatPanel({ isOpen, onClose, contextRunId, onClearContext }: ChatPanelProps) {
  const {
    sessionId,
    setSessionId,
    stream,
    send,
    startSession,
  } = useChat();

  const sessionsQuery = useChatSessions();
  const messagesQuery = useChatMessages(sessionId);
  const [panelWidth, setPanelWidth] = useState(420);
  const dragRef = useRef<{ startX: number; startW: number } | null>(null);

  useEffect(() => {
    if (contextRunId && isOpen) {
      startSession(contextRunId).then(() => {
        onClearContext();
        send(`Tell me about pipeline run ${contextRunId}. What went wrong?`);
      });
    }
  }, [contextRunId, isOpen, startSession, onClearContext, send]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startW: panelWidth };

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      const newW = Math.max(320, Math.min(window.innerWidth * 0.8, dragRef.current.startW + (dragRef.current.startX - ev.clientX)));
      setPanelWidth(newW);
    };
    const onMouseUp = () => {
      dragRef.current = null;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [panelWidth]);

  const handleNewChat = () => {
    startSession();
  };

  if (!isOpen) return null;

  const messages = messagesQuery.data?.messages ?? [];

  return (
    <div className="chat-panel" style={{ width: panelWidth }}>
      <div className="chat-resize-handle" onMouseDown={handleMouseDown} />

      <Flex
        justifyContent={{ default: 'justifyContentSpaceBetween' }}
        alignItems={{ default: 'alignItemsCenter' }}
        style={{ padding: '0.5rem 0.75rem' }}
      >
        <FlexItem>
          <Title headingLevel="h3" size="md">Chat</Title>
        </FlexItem>
        <FlexItem>
          <Button variant="plain" onClick={onClose} icon={<TimesIcon />} aria-label="Close chat" />
        </FlexItem>
      </Flex>

      <Flex
        spaceItems={{ default: 'spaceItemsSm' }}
        style={{ padding: '0 0.75rem 0.5rem' }}
      >
        <FlexItem grow={{ default: 'grow' }}>
          <FormSelect
            value={sessionId ?? ''}
            onChange={(_e, val) => setSessionId(val || null)}
            aria-label="Chat session"
          >
            <FormSelectOption value="" label="Select session..." />
            {sessionsQuery.data?.sessions.map((s) => (
              <FormSelectOption key={s.id} value={s.id} label={s.title ?? s.id.slice(0, 8)} />
            ))}
          </FormSelect>
        </FlexItem>
        <FlexItem>
          <Button variant="secondary" size="sm" onClick={handleNewChat}>New</Button>
        </FlexItem>
      </Flex>

      <Divider />

      <ChatMessages
        messages={messages}
        streamingText={stream.streamingText}
        isStreaming={stream.isStreaming}
        isThinking={stream.isThinking}
        toolCalls={stream.toolCalls}
        error={stream.error}
      />

      <Divider />

      <div style={{ padding: '0.5rem 0.75rem' }}>
        <ChatInput onSend={send} isDisabled={stream.isStreaming} />
      </div>
    </div>
  );
}
