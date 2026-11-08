"""Read-only, permissioned active opt-outs; no persistent plaintext phone index."""

from . import models as m
from .input_digits import ascii_digits
from .privacy import decrypt, digest, normalize_phone

PAGE_SIZE = 25


def resolve_phones(hashes):
    result = {}
    # Use only surviving encrypted identity sources. Never reconstruct a hash.
    for model, hash_field, cipher_field, ordering in [
        (m.Account, 'phone_hash', 'phone_cipher', '-created_at'),
        (m.Order, 'recipient_hash', 'recipient_cipher', '-created_at'),
        (m.Invitation, 'phone_hash', 'phone_cipher', '-created_at'),
    ]:
        missing = set(hashes) - result.keys()
        if not missing:
            break
        rows = model.objects.filter(**{hash_field + '__in': missing}).exclude(
            **{cipher_field: ''}
        )
        for key, cipher in (
            rows.order_by(ordering, '-pk')
            .values_list(hash_field, cipher_field)
            .iterator(chunk_size=500)
        ):
            if key not in result:
                result[key] = decrypt(cipher)
    return result


def blacklist_payload(actor, query, page):
    rows = m.RecipientState.objects.filter(blocked=True).order_by('-updated_at', '-pk')
    query = ascii_digits(query).strip()
    partial = ''
    if query:
        try:
            rows = rows.filter(phone_hash=digest(normalize_phone(query)))
        except ValueError:
            partial = (
                ''.join(query.split())
                .replace('-', '')
                .replace('(', '')
                .replace(')', '')
            )
            if not partial.isascii() or not partial.isdigit():
                rows = rows.none()
    selected = []
    total = 0

    def take(states):
        nonlocal total
        phones = resolve_phones([state.phone_hash for state in states])
        for state in states:
            phone = phones.get(state.phone_hash, '')
            if partial and partial not in phone:
                continue
            if (page - 1) * PAGE_SIZE <= total < page * PAGE_SIZE:
                selected.append(
                    {
                        'record_id': digest('management-blacklist:' + state.phone_hash),
                        'phone': phone or 'شماره در سوابق موجود نیست',
                        'blocked': True,
                        'updated_at': state.updated_at,
                    }
                )
            total += 1

    if partial:
        batch = []
        for state in rows.iterator(chunk_size=500):
            batch.append(state)
            if len(batch) == 500:
                take(batch)
                batch = []
        if batch:
            take(batch)
    else:
        total_count = rows.count()
        total = (page - 1) * PAGE_SIZE
        take(list(rows[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]))
        total = total_count
    m.OperatorAudit.objects.create(
        actor=actor,
        action='blacklist_viewed',
        object_id='blacklist',
        reason='مشاهدهٔ فهرست لغو دریافت در مدیریت',
        after={'page': page, 'returned': len(selected)},
    )
    return {
        'title': 'لیست سیاه',
        'columns': [
            {'key': 'phone', 'label': 'شمارهٔ لغوکننده', 'type': 'text'},
            {'key': 'blocked', 'label': 'دریافت مسدود', 'type': 'bool'},
            {'key': 'updated_at', 'label': 'آخرین به‌روزرسانی', 'type': 'date'},
        ],
        'rows': selected,
        'total': total,
        'page': page,
        'page_size': PAGE_SIZE,
        'statuses': [],
    }
