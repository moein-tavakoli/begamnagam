import { RecipientActions } from '@/components/recipient-actions';
import { privateMetadata } from '@/lib/seo';
export const metadata = privateMetadata('/r');
export default function Page() { return <RecipientActions />; }
