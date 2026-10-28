import { Wallet } from '@/components/wallet';
import { privateMetadata } from '@/lib/seo';
export const metadata = privateMetadata('/wallet');
export default function WalletPage() { return <Wallet />; }
