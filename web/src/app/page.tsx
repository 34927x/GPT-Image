import Link from 'next/link';
import { ArrowRight, Sparkles, Zap, Layers, Lock, Globe, Wand2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Logo } from '@/components/brand/logo';

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* HEADER */}
      <header className="sticky top-0 z-50 border-b border-border/40 backdrop-blur-xl bg-background/60">
        <div className="container flex h-16 items-center justify-between">
          <Logo />
          <div className="flex items-center gap-3">
            <Button asChild variant="ghost" size="sm">
              <Link href="/login">Sign in</Link>
            </Button>
            <Button asChild variant="gradient" size="sm">
              <Link href="/login">Get started</Link>
            </Button>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="relative pt-24 pb-32">
        <div className="container relative z-10 mx-auto max-w-5xl text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/40 px-4 py-1.5 text-xs backdrop-blur-sm">
            <Sparkles className="h-3 w-3 text-accent" />
            <span className="text-muted-foreground">Premium bulk image generator</span>
          </div>

          <h1 className="text-balance text-5xl font-bold tracking-tight sm:text-6xl md:text-7xl lg:text-8xl">
            Generate <span className="gradient-text">hundreds</span>
            <br />
            of AI images at once.
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-balance text-lg text-muted-foreground sm:text-xl">
            Bulk-GPT runs your prompts through rotating premium accounts so you never
            hit a rate limit again. Paste prompts, hit generate, walk away.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="xl" variant="gradient" className="group">
              <Link href="/login">
                Enter your access key
                <ArrowRight className="transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>
            <Button asChild size="xl" variant="outline">
              <Link href="#features">See how it works</Link>
            </Button>
          </div>
        </div>

        {/* Decorative gradient blob */}
        <div className="pointer-events-none absolute left-1/2 top-32 -z-0 -translate-x-1/2">
          <div className="h-96 w-[36rem] rounded-full bg-primary/20 blur-[160px]" />
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="border-t border-border/40 py-24">
        <div className="container mx-auto max-w-6xl">
          <div className="mb-16 text-center">
            <h2 className="text-balance text-3xl font-bold sm:text-4xl">
              Built for <span className="gradient-text">creators who ship</span>
            </h2>
            <p className="mt-4 text-muted-foreground">
              Everything you need for high-volume AI image production.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => (
              <div
                key={f.title}
                className="group relative overflow-hidden rounded-xl border border-border/60 bg-card/40 p-6 backdrop-blur-sm transition-all hover:border-primary/40 hover:bg-card/60"
              >
                <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="mb-2 font-semibold">{f.title}</h3>
                <p className="text-sm text-muted-foreground">{f.body}</p>
                <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-border/40 py-24">
        <div className="container mx-auto max-w-3xl text-center">
          <h2 className="text-balance text-3xl font-bold sm:text-4xl">
            Ready to ship at scale?
          </h2>
          <p className="mt-4 text-muted-foreground">
            Get an access key from your seller and start generating in under a minute.
          </p>
          <Button asChild size="xl" variant="gradient" className="mt-8">
            <Link href="/login">Enter your access key</Link>
          </Button>
        </div>
      </section>

      <footer className="border-t border-border/40 py-8">
        <div className="container flex flex-col items-center gap-4 text-sm text-muted-foreground sm:flex-row sm:justify-between">
          <Logo size="sm" />
          <p>© {new Date().getFullYear()} Bulk-GPT. Crafted by TurabCoder.</p>
        </div>
      </footer>
    </main>
  );
}

const features = [
  {
    icon: Layers,
    title: 'Bulk by default',
    body: 'Paste 100 prompts, get 100 images. Track every job in real time, retry the failures with one click.',
  },
  {
    icon: Zap,
    title: 'Rotating accounts',
    body: 'Hit a rate limit? The next premium account picks up automatically. No interruptions.',
  },
  {
    icon: Wand2,
    title: 'Smart prompt parsing',
    body: 'Multi-line prompts, blank-line separation, file upload — paste however you like.',
  },
  {
    icon: Lock,
    title: 'Key-based access',
    body: 'Your seller hands you a key. No accounts, no passwords, no extra setup.',
  },
  {
    icon: Globe,
    title: 'Live gallery',
    body: 'Every image you generate is saved to your private gallery. Download single, or zip the whole set.',
  },
  {
    icon: Sparkles,
    title: 'Premium UI',
    body: 'A dashboard you actually want to use. Built for shipping, not for fiddling.',
  },
];
