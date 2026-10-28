"""Private text access is deliberate, permissioned, and audited without content."""
from .models import OperatorAudit


def may_review_messages(actor):
    return (actor.is_active and actor.is_staff and actor.has_perm("core.view_order")
            and actor.has_perm("core.view_private_message_text"))


def message_texts(order):
    preview = order.preview
    return {"id": str(order.pk), "original_text": preview.original_text,
        "original_available": bool(preview.original_text),
        "final_text": preview.generated_body or preview.text or order.text,
        "mode": preview.moderation_mode}


def audit_review(actor, order, reason):
    OperatorAudit.objects.create(actor=actor, action="message_text_viewed",
        object_id=str(order.pk), reason=reason)
