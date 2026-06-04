import { Card, CardBody, CardTitle } from '@patternfly/react-core';
import type { DailyStats } from '../../api/types';
import './DailyChart.css';

interface DailyChartProps {
  data: DailyStats[];
}

const COLORS = {
  succeeded: '#51cf66',
  failed: '#ff6b6b',
  aborted: '#ffa94d',
};

export default function DailyChart({ data }: DailyChartProps) {
  if (!data.length) return null;

  const maxVal = Math.max(...data.map((d) => d.succeeded + d.failed + d.aborted), 1);

  const ySteps = 4;
  const yTicks = Array.from({ length: ySteps + 1 }, (_, i) => Math.round((maxVal * i) / ySteps));

  return (
    <Card isCompact>
      <CardTitle>Daily Runs</CardTitle>
      <CardBody>
        <div className="daily-chart">
          <div className="daily-chart-area">
            <div className="daily-y-axis">
              {[...yTicks].reverse().map((v) => (
                <span key={v} className="daily-y-label">{v}</span>
              ))}
            </div>
            <div className="daily-grid-and-bars">
              <div className="daily-gridlines">
                {yTicks.map((v) => (
                  <div
                    key={v}
                    className="daily-gridline"
                    style={{ bottom: `${(v / maxVal) * 100}%` }}
                  />
                ))}
              </div>
              <div className="daily-bars">
                {data.map((d) => {
                  const total = d.succeeded + d.failed + d.aborted;
                  const pct = (total / maxVal) * 100;
                  const [, m, day] = d.date.split('-');
                  const label = `${Number(m)}/${Number(day)}`;
                  return (
                    <div key={d.date} className="daily-bar-col" title={`${label}: ${d.succeeded}s / ${d.failed}f / ${d.aborted}a`}>
                      <div className="daily-bar-stack" style={{ height: `${pct}%` }}>
                        {d.succeeded > 0 && (
                          <div
                            className="daily-bar-segment"
                            style={{
                              flex: d.succeeded,
                              background: COLORS.succeeded,
                            }}
                          />
                        )}
                        {d.failed > 0 && (
                          <div
                            className="daily-bar-segment"
                            style={{
                              flex: d.failed,
                              background: COLORS.failed,
                            }}
                          />
                        )}
                        {d.aborted > 0 && (
                          <div
                            className="daily-bar-segment"
                            style={{
                              flex: d.aborted,
                              background: COLORS.aborted,
                            }}
                          />
                        )}
                      </div>
                      <span className="daily-x-label">{label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
          <div className="daily-legend">
            <span className="daily-legend-item">
              <span className="daily-legend-swatch" style={{ background: COLORS.succeeded }} />
              Succeeded
            </span>
            <span className="daily-legend-item">
              <span className="daily-legend-swatch" style={{ background: COLORS.failed }} />
              Failed
            </span>
            <span className="daily-legend-item">
              <span className="daily-legend-swatch" style={{ background: COLORS.aborted }} />
              Aborted
            </span>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
