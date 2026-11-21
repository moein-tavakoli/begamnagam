import { CreditPreviewReturn } from '@/components/credit-preview-return';
import { privateMetadata } from '@/lib/seo';

export const metadata = privateMetadata('/credits/review');

export default function Page() {
  return <CreditPreviewReturn/>;
}
