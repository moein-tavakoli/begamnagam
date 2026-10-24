"""Documented vendor protocols; network access is disabled unless configured."""
from .http import ProviderRejected, ProviderUnknown, ProviderDisabled
from .kavenegar import Kavenegar
from .zarinpal import Zarinpal
