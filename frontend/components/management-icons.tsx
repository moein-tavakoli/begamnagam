import MonitorHeartOutlined from '@mui/icons-material/MonitorHeartOutlined';
import DashboardOutlined from '@mui/icons-material/DashboardOutlined';
import PeopleOutlined from '@mui/icons-material/PeopleOutlined';
import BlockOutlined from '@mui/icons-material/BlockOutlined';
import SupportAgentOutlined from '@mui/icons-material/SupportAgentOutlined';
import ReceiptLongOutlined from '@mui/icons-material/ReceiptLongOutlined';
import AccountBalanceWalletOutlined from '@mui/icons-material/AccountBalanceWalletOutlined';
import AddCardOutlined from '@mui/icons-material/AddCardOutlined';
import Inventory2Outlined from '@mui/icons-material/Inventory2Outlined';
import CreditScoreOutlined from '@mui/icons-material/CreditScoreOutlined';
import SmsOutlined from '@mui/icons-material/SmsOutlined';
import OutboxOutlined from '@mui/icons-material/OutboxOutlined';
import ReportOutlined from '@mui/icons-material/ReportOutlined';
import FactCheckOutlined from '@mui/icons-material/FactCheckOutlined';
import PaymentsOutlined from '@mui/icons-material/PaymentsOutlined';
import CurrencyExchangeOutlined from '@mui/icons-material/CurrencyExchangeOutlined';
import AccountBalanceOutlined from '@mui/icons-material/AccountBalanceOutlined';
import SavingsOutlined from '@mui/icons-material/SavingsOutlined';
import NotificationsOutlined from '@mui/icons-material/NotificationsOutlined';
import HistoryOutlined from '@mui/icons-material/HistoryOutlined';
import SettingsOutlined from '@mui/icons-material/SettingsOutlined';
import TextSnippetOutlined from '@mui/icons-material/TextSnippetOutlined';
import CreditCardOutlined from '@mui/icons-material/CreditCardOutlined';
import AutoAwesomeOutlined from '@mui/icons-material/AutoAwesomeOutlined';
import PersonOutline from '@mui/icons-material/PersonOutlined';
import type { SvgIconProps } from '@mui/material/SvgIcon';

const icons = {
  dashboard:DashboardOutlined, monitoring:MonitorHeartOutlined, accounts:PeopleOutlined, blacklist:BlockOutlined,
  support:SupportAgentOutlined, 'manual-payments':ReceiptLongOutlined,
  'wallet-entries':AccountBalanceWalletOutlined, 'wallet-topups':AddCardOutlined,
  'credit-purchases':Inventory2Outlined, 'credit-entries':CreditScoreOutlined,
  orders:SmsOutlined, invitations:PeopleOutlined, 'invitation-sends':OutboxOutlined,
  'invitation-deliveries':SmsOutlined, deliveries:SmsOutlined, outbox:OutboxOutlined,
  reports:ReportOutlined, moderation:FactCheckOutlined, payments:PaymentsOutlined,
  refunds:CurrencyExchangeOutlined, 'financial-events':AccountBalanceOutlined,
  budgets:SavingsOutlined, alerts:NotificationsOutlined, audit:HistoryOutlined, changelog:HistoryOutlined,
  limits:SettingsOutlined, packages:Inventory2Outlined, examples:TextSnippetOutlined,
  'manual-settings':CreditCardOutlined, ai:AutoAwesomeOutlined,
};
export function ManagementIcon({name,...props}:SvgIconProps & {name:string}) {
  const Component = icons[name as keyof typeof icons] || PersonOutline;
  return <Component {...props} />;
}
