import type { Metadata } from 'next';
import { RecipientActions } from '@/components/recipient-actions';
export const metadata: Metadata = { title: 'انتخاب دریافت‌کننده', referrer: 'no-referrer', robots: {index:false, follow:false} };
export default function Page() { return <RecipientActions />; }
