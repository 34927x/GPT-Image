'use client';

import { useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { LogOut, Crown, BarChart3 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { logoutAction } from '@/app/login/actions';

export function Topbar({
  planName,
  keyName,
  totalUsed,
}: {
  planName: string;
  keyName: string;
  totalUsed?: number;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function logout() {
    startTransition(async () => {
      await logoutAction();
      toast.success('Signed out');
      router.push('/login');
      router.refresh();
    });
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border/40 bg-background/60 px-6 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <Badge variant="default" className="gap-1">
          <Crown className="h-3 w-3" />
          {planName}
        </Badge>
        {totalUsed !== undefined && (
          <Badge variant="outline" className="gap-1">
            <BarChart3 className="h-3 w-3" />
            {totalUsed} generated
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="hidden font-mono text-xs text-muted-foreground sm:inline">
          {keyName}
        </span>
        <Button onClick={logout} variant="outline" size="sm" disabled={isPending}>
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </div>
    </header>
  );
}
