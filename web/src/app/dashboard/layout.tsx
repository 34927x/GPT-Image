import { redirect } from 'next/navigation';
import { getCurrentKey } from '@/lib/auth';
import { Sidebar } from '@/components/dashboard/sidebar';
import { Topbar } from '@/components/dashboard/topbar';

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const current = await getCurrentKey();
  if (!current) redirect('/login');
  if (current.isAdmin) redirect('/admin');

  return (
    <div className="flex min-h-screen">
      <Sidebar isAdmin={false} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          planName={current.planName}
          keyName={current.key}
          totalUsed={current.record?.totalUsed ?? 0}
        />
        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
