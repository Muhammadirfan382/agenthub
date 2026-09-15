import type { ComponentProps } from 'react';
import { controlClasses } from './controlStyles';

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return <input className={controlClasses(`h-9 ${className ?? ''}`)} {...props} />;
}
