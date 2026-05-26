import Link from 'next/link';
import { redirect } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Logo } from '@/components/brand/logo';
import { LoginForm } from './login-form';
import { getCurrentKey } from '@/lib/auth';

export default async function LoginPage() {
  const current = await getCurrentKey();
  if (current) redirect(current.isAdmin ? '/admin' : '/dashboard');

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden p-4">
      {/* Decorative blob */}
      <div className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2">
        <div className="h-96 w-[40rem] rounded-full bg-primary/15 blur-[160px]" />
      </div>

      <Link
        href="/"
        className="absolute left-6 top-6 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to home
      </Link>

      <div className="relative w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Logo size="lg" />
        </div>

        <div className="gradient-border rounded-2xl p-8">
          <div className="mb-6 text-center">
            <h1 className="text-2xl font-semibold">Enter your access key</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Paste the key you received from your seller.
            </p>
          </div>
          <LoginForm />
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Don&apos;t have a key?{' '}
          <span className="text-foreground">Contact your seller.</span>
        </p>
      </div>
    </main>
  );
}
