import {
  Card,
  CardBody,
  CardTitle,
  Gallery,
  GalleryItem,
} from '@patternfly/react-core';
import type { StatsResponse } from '../../api/types';
import { formatPercent } from '../../utils/formatters';

interface StatsCardsProps {
  stats: StatsResponse;
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    { title: 'Total Runs', value: stats.total, color: undefined },
    { title: 'Failed', value: stats.failed, color: 'var(--pf-t--global--color--status--danger--default)' },
    { title: 'Pass Rate', value: formatPercent(stats.pass_rate), color: stats.pass_rate >= 80 ? 'var(--pf-t--global--color--status--success--default)' : 'var(--pf-t--global--color--status--danger--default)' },
    { title: 'Aborted', value: stats.aborted, color: 'var(--pf-t--global--color--status--warning--default)' },
  ];

  return (
    <Gallery hasGutter minWidths={{ default: '200px' }}>
      {cards.map((c) => (
        <GalleryItem key={c.title}>
          <Card isCompact>
            <CardTitle>{c.title}</CardTitle>
            <CardBody>
              <span style={{ fontSize: '2rem', fontWeight: 700, color: c.color }}>
                {c.value}
              </span>
            </CardBody>
          </Card>
        </GalleryItem>
      ))}
    </Gallery>
  );
}
