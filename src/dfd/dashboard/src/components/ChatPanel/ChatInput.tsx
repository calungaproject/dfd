import { useState, useRef } from 'react';
import { TextArea, Button, Flex, FlexItem } from '@patternfly/react-core';

interface ChatInputProps {
  onSend: (message: string) => void;
  isDisabled: boolean;
}

export default function ChatInput({ onSend, isDisabled }: ChatInputProps) {
  const [value, setValue] = useState('');
  const textRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const msg = value.trim();
    if (!msg) return;
    onSend(msg);
    setValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Flex spaceItems={{ default: 'spaceItemsSm' }} alignItems={{ default: 'alignItemsFlexEnd' }}>
      <FlexItem grow={{ default: 'grow' }}>
        <TextArea
          ref={textRef}
          value={value}
          onChange={(_e, val) => setValue(val)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about pipeline failures..."
          isDisabled={isDisabled}
          rows={2}
          resizeOrientation="vertical"
          aria-label="Chat message"
        />
      </FlexItem>
      <FlexItem>
        <Button
          variant="primary"
          onClick={handleSend}
          isDisabled={isDisabled || !value.trim()}
        >
          Send
        </Button>
      </FlexItem>
    </Flex>
  );
}
