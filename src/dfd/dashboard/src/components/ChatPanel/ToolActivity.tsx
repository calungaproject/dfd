import { Spinner, Flex, FlexItem } from '@patternfly/react-core';
import { formatToolCall } from '../../utils/formatters';

interface ToolActivityProps {
  name: string;
  input?: Record<string, unknown>;
  active: boolean;
}

export default function ToolActivity({ name, input, active }: ToolActivityProps) {
  return (
    <Flex
      spaceItems={{ default: 'spaceItemsSm' }}
      alignItems={{ default: 'alignItemsCenter' }}
      style={{
        padding: '0.25rem 0.5rem',
        fontSize: '0.85rem',
        color: 'var(--pf-t--global--text--color--subtle)',
        fontStyle: 'italic',
      }}
    >
      {active && (
        <FlexItem>
          <Spinner size="sm" />
        </FlexItem>
      )}
      <FlexItem>{formatToolCall(name, input)}</FlexItem>
    </Flex>
  );
}
