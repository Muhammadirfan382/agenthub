import { Monitor, Moon, Sun } from 'lucide-react';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Switch } from '@/components/ui/Switch';
import { cn } from '@/lib/cn';
import { type ThemePreference, useUiStore } from '@/stores/uiStore';

const THEMES: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
];

export function AppearanceSettings() {
  const theme = useUiStore((state) => state.theme);
  const setTheme = useUiStore((state) => state.setTheme);
  const collapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  return (
    <Card>
      <CardHeader title="Appearance" description="Stored in this browser." />
      <CardBody className="space-y-6">
        <fieldset>
          <legend className="text-sm font-medium text-fg">Theme</legend>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            {THEMES.map(({ value, label, icon: Icon }) => (
              <label
                key={value}
                className={cn(
                  'flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring',
                  theme === value ? 'border-brand bg-brand-soft text-brand-strong' : 'border-line text-fg hover:bg-surface-hover',
                )}
              >
                <input type="radio" name="theme" value={value} checked={theme === value} onChange={() => setTheme(value)} className="sr-only" />
                <Icon aria-hidden="true" className="size-4" />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        <Switch label="Collapse sidebar" description="Show icons only in the desktop sidebar." checked={collapsed} onCheckedChange={toggleSidebar} />
      </CardBody>
    </Card>
  );
}
