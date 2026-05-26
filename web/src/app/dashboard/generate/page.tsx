import { GeneratorClient } from './generator-client';

export default function GeneratePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Generate images</h1>
        <p className="mt-1 text-muted-foreground">
          Paste your prompts, pick a size, hit generate. Watch the gallery fill up live.
        </p>
      </div>
      <GeneratorClient />
    </div>
  );
}
