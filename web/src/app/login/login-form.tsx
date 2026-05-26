'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, KeyRound } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { loginAction } from './actions';

export function LoginForm() {
  const router = useRouter();
  const [key, setKey] = useState('');
  const [isPending, startTransition] = useTransition();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!key.trim()) {
      toast.error('Paste your access key first');
      return;
    }
    startTransition(async () => {
      const res = await loginAction(key.trim());
      if (res.success) {
        toast.success('Welcome back');
        router.push(res.redirect);
        router.refresh();
      } else {
        toast.error(res.error);
      }
    });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="relative">
        <KeyRound className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          autoFocus
          autoComplete="off"
          spellCheck={false}
          value={key}
          onChange={(e) => setKey(e.target.value.toUpperCase())}
          placeholder="BGT-XXXX-XXXX-XXXX"
          className="pl-10 font-mono tracking-wider uppercase"
          disabled={isPending}
        />
      </div>

      <Button
        type="submit"
        variant="gradient"
        size="lg"
        className="w-full"
        disabled={isPending}
      >
        {isPending ? <Loader2 className="animate-spin" /> : 'Continue'}
      </Button>
    </form>
  );
}
