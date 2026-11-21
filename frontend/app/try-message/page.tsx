import { TextTrial } from '@/components/text-trial';
import { privateMetadata } from '@/lib/seo';

export const metadata = privateMetadata('/try-message');

export default function Page() {
  return <TextTrial />;
}
