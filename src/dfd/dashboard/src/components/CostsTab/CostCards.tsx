import {
  Card,
  CardBody,
  CardTitle,
  Gallery,
  GalleryItem,
  Content,
} from '@patternfly/react-core';
import type { CostByType } from '../../api/types';
import { formatCost, formatTokens } from '../../utils/formatters';

interface CostCardsProps {
  data: CostByType[];
}

export default function CostCards({ data }: CostCardsProps) {
  const total = data.reduce((s, d) => s + d.total_cost, 0);

  return (
    <Gallery hasGutter minWidths={{ default: '200px' }}>
      <GalleryItem>
        <Card isCompact>
          <CardTitle>Total Spend</CardTitle>
          <CardBody>
            <span style={{ fontSize: '2rem', fontWeight: 700 }}>{formatCost(total)}</span>
          </CardBody>
        </Card>
      </GalleryItem>
      {data.map((d) => (
        <GalleryItem key={d.invocation_type}>
          <Card isCompact>
            <CardTitle>{d.invocation_type}</CardTitle>
            <CardBody>
              <span style={{ fontSize: '1.5rem', fontWeight: 700 }}>{formatCost(d.total_cost)}</span>
              <Content component="small" style={{ display: 'block', color: 'var(--pf-t--global--text--color--subtle)' }}>
                {d.calls} calls
                {d.input_tokens != null && <> · {formatTokens(d.input_tokens)} in</>}
                {d.output_tokens != null && <> · {formatTokens(d.output_tokens)} out</>}
              </Content>
            </CardBody>
          </Card>
        </GalleryItem>
      ))}
    </Gallery>
  );
}
