import { useId } from 'react';
import { useSearchParams } from 'react-router';
import { PageHeader } from '@/components/layout/PageHeader';
import { TabPanel, Tabs } from '@/components/ui/Tabs';
import { AgentPreferencesSettings } from './sections/AgentPreferencesSettings';
import { ApiSettings } from './sections/ApiSettings';
import { AppearanceSettings } from './sections/AppearanceSettings';
import { MembersSettings } from './sections/MembersSettings';
import { RuntimeSettings } from './sections/RuntimeSettings';
import { NotificationSettings } from './sections/NotificationSettings';
import { ProfileSettings } from './sections/ProfileSettings';
import { SecuritySettings } from './sections/SecuritySettings';

const SECTIONS = [
  { id: 'profile', label: 'Profile' },
  { id: 'appearance', label: 'Appearance' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'security', label: 'Security' },
  { id: 'members', label: 'Members' },
  { id: 'runtime', label: 'Runtime' },
  { id: 'api', label: 'API' },
  { id: 'agents', label: 'Agent preferences' },
] as const;

type SectionId = (typeof SECTIONS)[number]['id'];

export default function SettingsPage() {
  const idPrefix = useId();
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get('section');
  const section: SectionId = SECTIONS.some((s) => s.id === requested) ? (requested as SectionId) : 'profile';

  return (
    <>
      <PageHeader title="Settings" description="Your profile, appearance, notifications, security, members, runtime controls, API access and agent defaults." />
      <Tabs
        label="Settings sections"
        idPrefix={idPrefix}
        items={[...SECTIONS]}
        value={section}
        onChange={(next) => setSearchParams({ section: next }, { replace: true })}
      />
      <TabPanel idPrefix={idPrefix} id={section} className="max-w-3xl pt-6">
        {section === 'profile' && <ProfileSettings />}
        {section === 'appearance' && <AppearanceSettings />}
        {section === 'notifications' && <NotificationSettings />}
        {section === 'security' && <SecuritySettings />}
        {section === 'members' && <MembersSettings />}
        {section === 'runtime' && <RuntimeSettings />}
        {section === 'api' && <ApiSettings />}
        {section === 'agents' && <AgentPreferencesSettings />}
      </TabPanel>
    </>
  );
}
