import { Search } from 'lucide-react';
import type { ComponentProps } from 'react';
import { cn } from '@/lib/cn';
import { controlClasses } from './controlStyles';

interface SearchInputProps extends Omit<ComponentProps<'input'>, 'type'> {
  /** Required accessible name; placeholders are not labels. */
  label: string;
}

export function SearchInput({ label, className, ...props }: SearchInputProps) {
  return (
    <div className={cn('relative', className)}>
      <Search aria-hidden="true" className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle" />
      <input type="search" aria-label={label} className={controlClasses('h-9 pl-9')} {...props} />
    </div>
  );
}
