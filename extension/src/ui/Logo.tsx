export function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const cls = { sm: 'h-7 w-7', md: 'h-9 w-9', lg: 'h-12 w-12' }[size];
  const text = { sm: 'text-sm', md: 'text-base', lg: 'text-2xl' }[size];
  return (
    <div class="flex items-center gap-2">
      <div class={`${cls} relative grid place-items-center rounded-lg bg-gradient-to-br from-[hsl(263_80%_64%)] to-[hsl(188_95%_55%)]`}>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="white"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="h-1/2 w-1/2"
        >
          <path d="M9 18V5l12-2v13" />
          <circle cx="6" cy="18" r="3" />
          <circle cx="18" cy="16" r="3" />
        </svg>
      </div>
      <div class={`font-bold ${text}`}>
        Bulk<span class="gradient-text">GPT</span>
      </div>
    </div>
  );
}
