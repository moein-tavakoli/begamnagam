import re
from dataclasses import dataclass
from django.conf import settings
from .http import post, ProviderRejected, ProviderUnknown


@dataclass(frozen=True)
class SMSResult:
    status: str
    reference: str = ''
    cost_rial: int = 0


class Kavenegar:
    def _call(self, method, payload):
        key = settings.KAVENEGAR_API_KEY
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', key):
            raise ProviderRejected('missing_sms_key')
        result = post(settings.KAVENEGAR_BASE_URL, f'/v1/{key}/{method}.json', payload,
                      {'api.kavenegar.com'}, form=True)
        status = result.get('return', {}).get('status') if isinstance(result.get('return'), dict) else None
        if status != 200:
            if status in {400, 401, 402, 403, 404, 405, 406, 407, 411, 412, 413, 414, 416, 417, 418, 420, 422, 424, 426, 427, 429, 431, 432, 451, 501}:
                raise ProviderRejected(f'sms_rejected_{status}')
            raise ProviderUnknown('sms_unknown_response')
        entries = result.get('entries')
        if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
            raise ProviderUnknown('sms_ambiguous_entries')
        return entries[0]

    def _result(self, entry, *, local_id=None, message_id=None):
        try:
            ref = entry['messageid']
            if type(ref) is not int or ref <= 0:
                raise ValueError()
            if message_id and str(ref) != str(message_id):
                raise ValueError()
            if local_id is not None and str(entry.get('localid')) != str(local_id):
                raise ValueError()
            status = entry['status']
            if type(status) is not int:
                raise ValueError()
            cost = entry.get('cost', 0)
            if type(cost) is not int or cost < 0:
                raise ValueError()
        except (ValueError, KeyError):
            raise ProviderUnknown('sms_unbound_response') from None
        mapped = 'delivered' if status == 10 else 'failed' if status in {6, 11, 13, 14} else 'accepted' if status in {1, 2, 4, 5} else 'unknown'
        return SMSResult(mapped, str(ref), cost)

    def submit(self, *, phone, text, local_id):
        return self._result(self._call('sms/send', {'receptor': phone, 'message': text,
            'sender': settings.KAVENEGAR_SENDER, 'localid': local_id, 'hide': 1}))

    def status(self, *, local_id, message_id=''):
        # A missing local ID after the vendor's12h window is NOT permission to resend.
        method, payload = ('sms/status', {'messageid': message_id}) if message_id else ('sms/statuslocalmessageid', {'localid': local_id})
        entry = self._call(method, payload)
        return self._result(entry, message_id=message_id or None, local_id=None if message_id else local_id)

    def otp(self, *, phone, code):
        if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code):
            raise ProviderRejected('invalid_otp_code')
        if settings.KAVENEGAR_OTP_MODE == 'sms':
            # Fixed server-owned text; never dispatch user input through the OTP path.
            return self._result(self._call('sms/send', {'receptor': phone,
                'message': f'بگم نگم\nکد ورود: {code}\nاعتبار: ۵ دقیقه\nکد را در اختیار کسی نگذارید.',
                'sender': settings.KAVENEGAR_SENDER, 'hide': 1}))
        if settings.KAVENEGAR_OTP_MODE == 'lookup' and settings.KAVENEGAR_OTP_TEMPLATE:
            return self._result(self._call('verify/lookup', {'receptor': phone, 'token': code,
                'template': settings.KAVENEGAR_OTP_TEMPLATE, 'type': 'sms'}))
        raise ProviderRejected('invalid_otp_configuration')
