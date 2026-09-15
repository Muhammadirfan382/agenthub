import { Monitor, Moon, Sun } from 'lucide-react';
import { DropdownMenu } from '@/components/ui/DropdownMenu';
import { type ThemePreference, useUiStore } from '@/stores/uiStore';

const OPTIONS: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
];

export function ThemeToggle() {
  const theme = useUiStore((state) => state.theme);
  const setTheme = useUiStore((state) => state.setTheme);
  const current = OPTIONS.find((option) => option.value === theme) ?? OPTIONS[2];
  const Icon = current?.icon ?? Monitor;

  return (
    <DropdownMenu
      label={`Theme: ${current?.label ?? 'System'}`}
      trigger={<Icon aria-hidden="true" className="size-4" />}
      items={OPTIONS.map((option) => ({
        id: option.value,
        label: option.value === theme ? `${option.label} (current)` : option.label,
        icon: option.icon,
        onSelect: () => setTheme(option.value),
      }))}
    />
  );
}
