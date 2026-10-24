import re
from dataclasses import dataclass
from django.conf import settings
from .http import post, endpoint, ProviderRejected, ProviderUnknown


@dataclass(frozen=True)
class PaymentRequest:
    authority: str
    redirect_url: str


@dataclass(frozen=True)
class VerifiedPayment:
    reference: str


def rial(toman):
    if type(toman) is not int or toman <= 0:
        raise ValueError('positive_integer_toman_required')
    return toman * 10


class Zarinpal:
    def _call(self, method, payload):
        payload = {'merchant_id': settings.ZARINPAL_MERCHANT_ID, **payload}
        result = post(settings.ZARINPAL_BASE_URL, f'/pg/v4/payment/{method}.json', payload,
                      {'payment.zarinpal.com', 'api.zarinpal.com', 'sandbox.zarinpal.com'})
        data = result.get('data')
        if isinstance(data, dict) and type(data.get('code')) is int and data['code'] in ({100, 101} if method == 'verify' else {100}):
            return data
        errors = result.get('errors')
        code = errors.get('code') if isinstance(errors, dict) else data.get('code') if isinstance(data, dict) else None
        if type(code) is int and code in {-9, -10, -11, -12, -15, -16, -17, -30, -31, -32, -33, -34, -35, -36, -37, -38, -39, -40, -50, -51, -52, -53, -54, -60, -61, -62}:
            raise ProviderRejected(f'payment_rejected_{abs(code)}')
        raise ProviderUnknown('payment_unknown_response')

    def request(self, *, amount_toman, callback_url):
        data = self._call('request', {'amount': rial(amount_toman), 'currency': 'IRR',
            'callback_url': callback_url, 'description': 'خدمت بگم نگم'})
        authority = data.get('authority')
        if not isinstance(authority, str) or not re.fullmatch(r'[AS][A-Za-z0-9]{15,63}', authority):
            raise ProviderUnknown('invalid_authority')
        url = endpoint(settings.ZARINPAL_REDIRECT_BASE, '/pg/StartPay/' + authority,
                       {'www.zarinpal.com', 'sandbox.zarinpal.com'})
        return PaymentRequest(authority, url)

    def verify(self, *, authority, amount_toman):
        data = self._call('verify', {'authority': authority, 'amount': rial(amount_toman)})
        ref = data.get('ref_id')
        if type(ref) not in {str, int} or not re.fullmatch(r'[0-9]{1,30}', str(ref)):
            raise ProviderUnknown('verification_missing_reference')
        # Some environments return amount/currency; reject mismatches if present.
        if 'amount' in data and (type(data['amount']) is not int or data['amount'] != rial(amount_toman)):
            raise ProviderRejected('amount_mismatch')
        if data.get('currency', 'IRR') != 'IRR':
            raise ProviderRejected('currency_mismatch')
        return VerifiedPayment(str(ref))

    def inquire(self, *, authority):
        data = self._call('inquiry', {'authority': authority})
        state = data.get('status')
        if state not in {'VERIFIED', 'PAID', 'IN_BANK', 'FAILED', 'REVERSED'}:
            raise ProviderUnknown('payment_unknown_status')
        return state

    def reverse(self, *, authority):
        # Only the documented pre-settlement reversal. Later refunds are a tracked
        # manual obligation until the merchant's refund API/contract is configured.
        self._call('reverse', {'authority': authority})
        return authority
