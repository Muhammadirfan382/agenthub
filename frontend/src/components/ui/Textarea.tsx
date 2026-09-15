import type { ComponentProps } from 'react';
import { controlClasses } from './controlStyles';

export function Textarea({ className, rows = 4, ...props }: ComponentProps<'textarea'>) {
  return <textarea rows={rows} className={controlClasses(`min-h-20 py-2 leading-relaxed ${className ?? ''}`)} {...props} />;
}
