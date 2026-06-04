import { Card, CardBody, CardTitle } from '@patternfly/react-core';
import type { DailyCost } from '../../api/types';
import './CostChart.css';

interface CostChartProps {
  data: DailyCost[];
}

const TYPE_COLORS: Record<string, string> = {
  analysis: '#6c8aff',
  reanalysis: '#51cf66',
  chat: '#ffd43b',
  dedup: '#8b90a0',
};

export default function CostChart({ data }: CostChartProps) {
  if (!data.length) return null;

  const types = [...new Set(data.map((d) => d.invocation_type))];
  const days = [...new Set(data.map((d) => d.day))].sort();

  const dayTotals = new Map<string, Map<string, number>>();
  for (const d of data) {
    if (!dayTotals.has(d.day)) dayTotals.set(d.day, new Map());
    dayTotals.get(d.day)!.set(d.invocation_type, d.cost);
  }

  const maxVal = Math.max(
    ...days.map((day) => {
      const m = dayTotals.get(day)!;
      let sum = 0;
      for (const v of m.values()) sum += v;
      return sum;
    }),
    0.01,
  );

  const ySteps = 4;
  const yTicks = Array.from({ length: ySteps + 1 }, (_, i) => (maxVal * i) / ySteps);

  return (
    <Card isCompact>
      <CardTitle>Daily Costs</CardTitle>
      <CardBody>
        <div className="cost-chart">
          <div className="cost-chart-area">
            <div className="cost-y-axis">
              {[...yTicks].reverse().map((v, i) => (
                <span key={i} className="cost-y-label">${v.toFixed(2)}</span>
              ))}
            </div>
            <div className="cost-grid-and-bars">
              <div className="cost-gridlines">
                {yTicks.map((v, i) => (
                  <div
                    key={i}
                    className="cost-gridline"
                    style={{ bottom: `${(v / maxVal) * 100}%` }}
                  />
                ))}
              </div>
              <div className="cost-bars">
                {days.map((day) => {
                  const m = dayTotals.get(day)!;
                  let total = 0;
                  for (const v of m.values()) total += v;
                  const pct = (total / maxVal) * 100;
                  const [, mon, dd] = day.split('-');
                  const label = `${Number(mon)}/${Number(dd)}`;
                  const tooltip = types
                    .map((t) => `${t}: $${(m.get(t) ?? 0).toFixed(4)}`)
                    .join('\n');
                  return (
                    <div key={day} className="cost-bar-col" title={tooltip}>
                      <div className="cost-bar-stack" style={{ height: `${pct}%` }}>
                        {types.map((t) => {
                          const val = m.get(t) ?? 0;
                          if (val <= 0) return null;
                          return (
                            <div
                              key={t}
                              className="cost-bar-segment"
                              style={{
                                flex: val,
                                background: TYPE_COLORS[t] ?? '#8b90a0',
                              }}
                            />
                          );
                        })}
                      </div>
                      <span className="cost-x-label">{label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
          <div className="cost-legend">
            {types.map((t) => (
              <span key={t} className="cost-legend-item">
                <span
                  className="cost-legend-swatch"
                  style={{ background: TYPE_COLORS[t] ?? '#8b90a0' }}
                />
                {t}
              </span>
            ))}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
