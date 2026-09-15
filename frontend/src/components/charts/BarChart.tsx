import { cn } from '@/lib/cn';

export interface BarDatum {
  label: string;
  value: number;
}

interface BarChartProps {
  data: BarDatum[];
  /** Accessible description of what the chart shows. */
  title: string;
  formatValue?: (value: number) => string;
  height?: number;
  className?: string;
}

/**
 * Dependency-free bar chart. The visual is hidden from assistive technology
 * and an equivalent data table is provided instead.
 */
export function BarChart({ data, title, formatValue = String, height = 160, className }: BarChartProps) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <figure className={cn('w-full', className)}>
      <div aria-hidden="true" className="flex items-end gap-1.5" style={{ height }}>
        {data.map((d) => (
          <div key={d.label} className="group flex h-full min-w-0 flex-1 flex-col justify-end" title={`${d.label}: ${formatValue(d.value)}`}>
            <div className="w-full rounded-t-sm bg-brand/80 transition-colors group-hover:bg-brand" style={{ height: `${Math.max(2, (d.value / max) * 100)}%` }} />
          </div>
        ))}
      </div>
      <div aria-hidden="true" className="mt-2 flex justify-between text-[11px] text-fg-subtle">
        <span>{data[0]?.label}</span>
        <span>{data[data.length - 1]?.label}</span>
      </div>
      <table className="sr-only">
        <caption>{title}</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.label}>
              <th scope="row">{d.label}</th>
              <td>{formatValue(d.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
