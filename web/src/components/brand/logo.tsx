import { cn } from '@/lib/utils';

export function Logo({ className, size = 'md' }: { className?: string; size?: 'sm' | 'md' | 'lg' }) {
  const sizes = {
    sm: { box: 'h-7 w-7', text: 'text-base' },
    md: { box: 'h-9 w-9', text: 'text-lg' },
    lg: { box: 'h-12 w-12', text: 'text-2xl' },
  };
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <div
        className={cn(
          'relative grid place-items-center rounded-lg bg-gradient-to-br from-primary to-accent shadow-lg shadow-primary/30',
          sizes[size].box
        )}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-1/2 w-1/2"
        >
          <path d="M9 18V5l12-2v13" />
          <circle cx="6" cy="18" r="3" />
          <circle cx="18" cy="16" r="3" />
        </svg>
        <span className="absolute inset-0 rounded-lg bg-gradient-to-br from-primary to-accent opacity-50 blur-xl" />
      </div>
      <div className="flex flex-col leading-none">
        <span className={cn('font-bold tracking-tight', sizes[size].text)}>
          Bulk<span className="gradient-text">GPT</span>
        </span>
      </div>
    </div>
  );
}
