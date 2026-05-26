'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Home,
  Wand2,
  Image as ImageIcon,
  Settings,
  Shield,
  KeyRound,
  Activity,
  Cpu,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Logo } from '@/components/brand/logo';

const userNav = [
  { href: '/dashboard', label: 'Overview', icon: Home },
  { href: '/dashboard/generate', label: 'Generate', icon: Wand2 },
  { href: '/dashboard/gallery', label: 'Gallery', icon: ImageIcon },
  { href: '/dashboard/settings', label: 'Settings', icon: Settings },
];

const adminNav = [
  { href: '/admin', label: 'Overview', icon: Activity },
  { href: '/admin/keys', label: 'Access keys', icon: KeyRound },
  { href: '/admin/plans', label: 'Plans', icon: Shield },
  { href: '/admin/workers', label: 'Workers', icon: Cpu },
  { href: '/admin/gallery', label: 'All images', icon: ImageIcon },
];

export function Sidebar({ isAdmin }: { isAdmin: boolean }) {
  const pathname = usePathname();
  const nav = isAdmin ? adminNav : userNav;

  return (
    <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border/40 bg-card/30 backdrop-blur-xl lg:flex">
      <div className="flex h-16 items-center border-b border-border/40 px-6">
        <Logo size="sm" />
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {nav.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== '/dashboard' &&
              item.href !== '/admin' &&
              pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all',
                isActive
                  ? 'bg-primary/15 text-foreground border border-primary/30 shadow-sm shadow-primary/20'
                  : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground'
              )}
            >
              <item.icon
                className={cn(
                  'h-4 w-4 transition-colors',
                  isActive ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground'
                )}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {isAdmin && (
        <div className="border-t border-border/40 p-3">
          <Link
            href="/dashboard"
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
          >
            <Home className="h-4 w-4" />
            User view
          </Link>
        </div>
      )}
    </aside>
  );
}
