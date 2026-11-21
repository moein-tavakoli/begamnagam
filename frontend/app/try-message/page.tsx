import { TextTrial } from '@/components/text-trial';
import { trialExampleDraft } from '@/lib/purchase-examples';
import { privateMetadata } from '@/lib/seo';

export const metadata = privateMetadata('/try-message');

export default async function Page({ searchParams }: {
  searchParams: Promise<{ example?: string | string[] }>;
}) {
  const { example } = await searchParams;
  const initialDraft = trialExampleDraft(example);
  return <TextTrial key={initialDraft} initialDraft={initialDraft} />;
}
