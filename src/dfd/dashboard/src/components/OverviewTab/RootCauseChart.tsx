import { Card, CardBody, CardTitle } from '@patternfly/react-core';
import type { RootCauseStat } from '../../api/types';
import './RootCauseChart.css';

interface RootCauseChartProps {
  data: RootCauseStat[];
}

const BAR_COLORS = [
  '#ff6b6b', '#ffa94d', '#ffd43b', '#69dbff',
  '#b197fc', '#6c8aff', '#51cf66',
];

export default function RootCauseChart({ data }: RootCauseChartProps) {
  if (!data.length) return null;

  const sorted = [...data].sort((a, b) => b.count - a.count).slice(0, 15);
  const total = sorted.reduce((s, r) => s + r.count, 0);

  return (
    <Card isCompact>
      <CardTitle>Root Causes</CardTitle>
      <CardBody>
        <div className="root-cause-bars">
          {sorted.map((rc, i) => {
            const pct = total > 0 ? Math.round((rc.count / total) * 100) : 0;
            const color = BAR_COLORS[i % BAR_COLORS.length]!;
            return (
              <div key={rc.root_cause} className="bar-row">
                <div className="bar-label" title={rc.root_cause}>
                  {rc.root_cause}
                </div>
                <div className="bar-track">
                  <div
                    className="bar-fill"
                    style={{ width: `${pct}%`, background: color }}
                  />
                </div>
                <div className="bar-count">
                  {rc.count} ({pct}%)
                </div>
              </div>
            );
          })}
        </div>
      </CardBody>
    </Card>
  );
}
