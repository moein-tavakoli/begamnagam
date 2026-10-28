"""Shared, versioned AI settings. Credentials and URLs remain server-owned."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import AIConfiguration, OperatorAudit
from .services import APIError

FIELDS = ('provider', 'ollama_model', 'gapgpt_model', 'timeout_seconds',
          'parallel_requests', 'daily_limit', 'user_daily_limit',
          'tone_polite_enabled', 'tone_firm_enabled', 'tone_angry_enabled')


def current():
    return AIConfiguration.objects.filter(pk=1).first() or AIConfiguration(
        provider=settings.AI_MODE, ollama_model=settings.OLLAMA_MODEL,
        gapgpt_model=settings.GAPGPT_MODEL)


def values(config):
    return {name: getattr(config, name) for name in FIELDS}


def available(config=None):
    config = config or current()
    if config.provider == 'ollama':
        return True
    from .limits import policy
    limits = policy()
    return (config.provider == 'gapgpt' and bool(settings.GAPGPT_API_KEY)
            and bool(config.gapgpt_model or settings.GAPGPT_MODEL)
            and (limits.rewrite_daily_unlimited or limits.rewrite_daily_limit > 0)
            and limits.rewrite_user_limit > 0)


@transaction.atomic
def update(actor, incoming, revision, reason):
    from .limit_services import validate_reason
    if not actor.is_active or not actor.is_staff or not actor.has_perm('core.manage_ai'):
        raise APIError('forbidden', 'مجوز تغییر هوش مصنوعی را ندارید.', 403)
    reason = validate_reason(reason)
    if (not isinstance(incoming, dict) or not incoming or set(incoming) - set(FIELDS)
            or type(revision) is not int or revision < 0):
        raise APIError('invalid_input', 'تنظیمات هوش مصنوعی معتبر نیست.', 422)
    initial = current()
    config, _ = AIConfiguration.objects.get_or_create(pk=1, defaults=values(initial))
    config = AIConfiguration.objects.select_for_update().get(pk=1)
    if config.revision != revision:
        raise APIError('settings_changed', 'تنظیمات تغییر کرده است؛ تازه‌سازی کن.', 409)
    before = values(config)
    for name, value in incoming.items():
        expected = bool if name.startswith('tone_') else str if name in FIELDS[:3] else int
        if type(value) is not expected:
            raise APIError('invalid_settings', 'نوع مقدار معتبر نیست.', 422, {name: ['مقدار معتبر وارد کن.']})
        setattr(config, name, value)
    try:
        config.full_clean()
        if config.provider == 'gapgpt' and not available(config):
            raise ValidationError({'provider': 'کلید، مدل، سقف مثبت هر حساب و سقف مثبت سایت یا گزینهٔ بدون سقف GapGPT باید آماده باشند.'})
    except ValidationError as error:
        raise APIError('invalid_settings', 'تنظیمات مشخص‌شده را اصلاح کن.', 422, error.message_dict) from None
    if before != values(config) or not config.revision:
        config.revision += 1
        config.save()
        OperatorAudit.objects.create(actor=actor, action='update_ai_configuration', object_id='ai:1',
                                     reason=reason, before=before, after=values(config))
    return config
