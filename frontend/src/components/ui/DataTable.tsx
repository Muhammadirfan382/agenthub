import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';
import type { ReactNode } from 'react';
import { DESKTOP_QUERY, useMediaQuery } from '@/hooks/useMediaQuery';
import { cn } from '@/lib/cn';

export interface ColumnSort {
  direction: 'asc' | 'desc' | null;
  onToggle: () => void;
}

export interface Column<T> {
  id: string;
  header: string;
  cell: (row: T) => ReactNode;
  align?: 'left' | 'right';
  className?: string;
  sort?: ColumnSort;
  /** The column used as the card title on small screens. */
  primary?: boolean;
  hideOnMobile?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  /** Describes the table for screen readers. */
  caption: string;
}

/**
 * A real <table> on wider screens; stacked cards on phones. Only one layout is
 * rendered, so content is never duplicated for assistive technology.
 */
export function DataTable<T>({ columns, rows, getRowKey, caption }: DataTableProps<T>) {
  const desktop = useMediaQuery(DESKTOP_QUERY);
  return desktop ? (
    <TableLayout columns={columns} rows={rows} getRowKey={getRowKey} caption={caption} />
  ) : (
    <CardLayout columns={columns} rows={rows} getRowKey={getRowKey} caption={caption} />
  );
}

function TableLayout<T>({ columns, rows, getRowKey, caption }: DataTableProps<T>) {
  return (
    <div tabIndex={0} role="region" aria-label={caption} className="overflow-x-auto rounded-lg border border-line bg-surface shadow-card focus-visible:outline-2 focus-visible:outline-ring">
      <table className="w-full min-w-[640px] text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="border-b border-line bg-surface-muted">
          <tr>
            {columns.map((column) => (
              <th
                key={column.id}
                scope="col"
                aria-sort={column.sort?.direction === 'asc' ? 'ascending' : column.sort?.direction === 'desc' ? 'descending' : undefined}
                className={cn('px-4 py-2.5 text-xs font-semibold tracking-wide whitespace-nowrap text-fg-muted uppercase', column.align === 'right' && 'text-right')}
              >
                {column.sort ? <SortButton label={column.header} sort={column.sort} /> : column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row) => (
            <tr key={getRowKey(row)} className="transition-colors hover:bg-surface-muted/60">
              {columns.map((column) => (
                <td key={column.id} className={cn('px-4 py-3 align-middle', column.align === 'right' && 'text-right', column.className)}>
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SortButton({ label, sort }: { label: string; sort: ColumnSort }) {
  const Icon = sort.direction === 'asc' ? ArrowUp : sort.direction === 'desc' ? ArrowDown : ArrowUpDown;
  return (
    <button
      type="button"
      onClick={sort.onToggle}
      className="inline-flex items-center gap-1 rounded uppercase hover:text-fg focus-visible:outline-2 focus-visible:outline-ring"
    >
      {label}
      <Icon aria-hidden="true" className="size-3.5" />
      <span className="sr-only">, change sort order</span>
    </button>
  );
}

function CardLayout<T>({ columns, rows, getRowKey, caption }: DataTableProps<T>) {
  const primary = columns.find((c) => c.primary) ?? columns[0];
  const rest = columns.filter((c) => c !== primary && !c.hideOnMobile);
  return (
    <ul aria-label={caption} className="space-y-3">
      {rows.map((row) => (
        <li key={getRowKey(row)} className="rounded-lg border border-line bg-surface p-4 shadow-card">
          {primary && <div className="mb-3 min-w-0">{primary.cell(row)}</div>}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
            {rest.map((column) => (
              <div key={column.id} className={cn('min-w-0', column.align === 'right' && 'col-span-2')}>
                {column.header && <dt className="text-xs text-fg-subtle">{column.header}</dt>}
                <dd className="mt-0.5 min-w-0 text-sm">{column.cell(row)}</dd>
              </div>
            ))}
          </dl>
        </li>
      ))}
    </ul>
  );
}
