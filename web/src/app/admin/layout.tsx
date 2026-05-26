import { redirect } from 'next/navigation';
import { getCurrentKey } from '@/lib/auth';
import { Sidebar } from '@/components/dashboard/sidebar';
import { Topbar } from '@/components/dashboard/topbar';

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const current = await getCurrentKey();
  if (!current) redirect('/login');
  if (!current.isAdmin) redirect('/dashboard');

  return (
    <div className="flex min-h-screen">
      <Sidebar isAdmin />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar planName="Admin" keyName={current.key} />
        <main className="flex-1 overflow-y-auto p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
