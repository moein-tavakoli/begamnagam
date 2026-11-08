"""Owner-managed application roles; never grant Django auth administration."""
import unicodedata
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import OperatorAudit, StaffMembership, StaffRole
from .services import APIError


SECTION_CATALOG = (
    {'key': 'support', 'label': 'پشتیبانی',
     'description': 'مشاهدهٔ صندوق گفت‌وگوهای خصوصی، پاسخ، ثبت خواندن و بستن گفت‌وگو.'},
    {'key': 'finance', 'label': 'مالی',
     'description': 'مشاهدهٔ رسیدها، خرید اعتبار، گردش کیف پول، پرداخت و خلاصهٔ سفارش؛ تأیید رسید و بازپرداخت مستند.'},
    {'key': 'operations', 'label': 'عملیات',
     'description': 'مانیتورینگ، صف پیام و دعوت، وضعیت تحویل، هزینهٔ پیامک، هشدارها و توقف یا ازسرگیری ارسال.'},
    {'key': 'users', 'label': 'کاربران',
     'description': 'مشاهدهٔ شمارهٔ کاربران، دعوت‌ها و لیست سیاه؛ تعلیق حساب و تنظیم سقف، اعتبار رایگان و لحن اختصاصی.'},
    {'key': 'content', 'label': 'محتوا',
     'description': 'مشاهدهٔ کاربران و سابقهٔ پیام برای بررسی متن‌های خصوصی و ورودی‌های ردشده، رسیدگی به گزارش‌ها و مدیریت پیام‌های نمونه.'},
    {'key': 'settings', 'label': 'تنظیمات',
     'description': 'تنظیم محدودیت‌ها، هوش مصنوعی، بسته‌ها و کانال کارت‌به‌کارت؛ مشاهدهٔ سوابق مدیران و تاریخچهٔ تغییرات.'},
)

# Explicit allowlist: no generated permissions and no auth user/group privileges.
SECTION_PERMISSIONS = {
    'support': ('view_supportconversation', 'add_supportmessage'),
    'finance': ('view_manualpayment', 'approve_manual_payments', 'view_walletentry', 'view_wallettopup',
        'view_creditpurchase', 'view_creditentry', 'view_paymentattempt', 'view_refund',
        'view_financialevent', 'view_order', 'confirm_refund'),
    'operations': ('view_operations', 'view_order', 'view_messagedelivery', 'view_outbox',
        'view_invitationsend', 'view_spendbudget', 'view_operationalalert', 'view_safetycontrol', 'operate_safety'),
    'users': ('view_account', 'view_recipientstate', 'view_invitation', 'view_invitationsend',
        'suspend_account', 'manage_account_limits', 'manage_free_sending', 'manage_message_tone'),
    'content': ('view_account', 'view_order', 'view_abusereport', 'view_moderationaudit',
        'triage_report', 'view_private_message_text', 'manage_message_examples'),
    'settings': ('manage_site_limits', 'manage_ai', 'manage_message_packages',
        'manage_manual_payments', 'view_operatoraudit'),
}


def owner_required(actor):
    if not actor.is_active or not actor.is_staff or not actor.is_superuser:
        raise APIError('forbidden', 'فقط مدیر اصلی می‌تواند کارمندان و نقش‌ها را مدیریت کند.', 403)


def can_support(actor):
    if not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        return False
    return actor.is_superuser or not StaffMembership.objects.filter(user=actor).exists() or actor.has_perms(
        ('core.view_supportconversation', 'core.add_supportmessage'))


def can_view_changelog(actor):
    if not actor.is_authenticated or not actor.is_active or not actor.is_staff:
        return False
    if actor.is_superuser:
        return True
    membership = StaffMembership.objects.select_related('role').filter(user=actor).first()
    return membership is None or 'settings' in membership.role.sections


def invalid_input():
    raise APIError('invalid_input', 'اطلاعات کارمند یا نقش معتبر نیست.', 422)


def strict_fields(data, required, optional=()):
    if not isinstance(data, dict) or set(data) - (set(required) | set(optional)) or set(required) - set(data):
        invalid_input()


def revision_value(data):
    value = data.get('revision')
    if type(value) is not int or not 0 <= value <= 2147483647:
        invalid_input()
    return value


def check_revision(expected, current):
    if expected != current:
        raise APIError('revision_conflict', 'اطلاعات تغییر کرده است؛ فهرست را تازه کنید.', 409)


def clean_name(value, maximum):
    if not isinstance(value, str) or len(value) > maximum:
        invalid_input()
    value = unicodedata.normalize('NFC', value).strip()
    if not value or any(unicodedata.category(c) in {'Cc', 'Cs'} for c in value):
        invalid_input()
    return value


def role_values(data):
    name = clean_name(data.get('name'), 80)
    sections = data.get('sections')
    if not isinstance(sections, list) or not sections or any(
            not isinstance(s, str) or s not in SECTION_PERMISSIONS for s in sections):
        invalid_input()
    if len(set(sections)) != len(sections):
        invalid_input()
    return name, [s['key'] for s in SECTION_CATALOG if s['key'] in sections]


def sync_permissions(role):
    codenames = {p for section in role.sections for p in SECTION_PERMISSIONS[section]}
    permissions = list(Permission.objects.filter(content_type__app_label='core', codename__in=codenames))
    if {p.codename for p in permissions} != codenames:
        # Missing installation permissions must never produce a partly active role.
        raise APIError('service_unavailable', 'مجوزهای نقش آماده نیستند.', 503)
    role.group.permissions.set(permissions)


def role_data(role):
    return {'id': role.pk, 'name': role.name, 'sections': role.sections, 'revision': role.revision,
        'member_count': role.memberships.count()}


def employee_data(user):
    membership = StaffMembership.objects.select_related('role').filter(user=user).first()
    return {'id': user.pk, 'username': user.get_username(), 'display_name': user.get_full_name(),
        'role': {'id': membership.role_id, 'name': membership.role.name} if membership else None,
        'is_active': user.is_active, 'is_owner': user.is_superuser,
        'revision': membership.revision if membership else 0}


def audit(actor, action, object_id, before, after):
    OperatorAudit.objects.create(actor=actor, action=action, object_id=str(object_id),
        reason='مدیریت کارمندان و نقش‌ها توسط مدیر اصلی', before=before, after=after)


@transaction.atomic
def create_role(actor, data):
    owner_required(actor)
    strict_fields(data, ('name', 'sections'))
    name, sections = role_values(data)
    try:
        with transaction.atomic():
            group = Group.objects.create(name='_begamnagam_staff_role_' + uuid.uuid4().hex)
            role = StaffRole.objects.create(name=name, group=group, sections=sections)
    except IntegrityError:
        raise APIError('duplicate_name', 'این نام نقش قبلاً ثبت شده است.', 409) from None
    sync_permissions(role)
    audit(actor, 'staff_role_created', role.pk, {}, {'sections': sections})
    return role_data(role)


@transaction.atomic
def update_role(actor, role_id, data):
    owner_required(actor)
    strict_fields(data, ('name', 'sections', 'revision'))
    revision = revision_value(data)
    name, sections = role_values(data)
    role = StaffRole.objects.select_for_update().get(pk=role_id)
    check_revision(revision, role.revision)
    before = {'sections': role.sections}
    role.name, role.sections, role.revision = name, sections, role.revision + 1
    try:
        with transaction.atomic():
            role.save(update_fields=['name', 'sections', 'revision'])
    except IntegrityError:
        raise APIError('duplicate_name', 'این نام نقش قبلاً ثبت شده است.', 409) from None
    sync_permissions(role)
    audit(actor, 'staff_role_updated', role.pk, before, {'sections': sections})
    return role_data(role)


@transaction.atomic
def delete_role(actor, role_id, data):
    owner_required(actor)
    strict_fields(data, ('revision',))
    revision = revision_value(data)
    role = StaffRole.objects.select_for_update().get(pk=role_id)
    check_revision(revision, role.revision)
    # Include inactive members; no employee may be left without a role.
    if role.memberships.exists() or role.group.user_set.exists():
        raise APIError('role_in_use', 'نقش دارای کارمند است؛ ابتدا نقش کارمندان را تغییر دهید.', 409)
    role_id, group = role.pk, role.group
    before = {'sections': role.sections}
    role.delete()
    group.delete()
    audit(actor, 'staff_role_deleted', role_id, before, {})
    return {'ok': True}


def employee_values(data):
    display_name = clean_name(data.get('display_name'), 150)
    role_id, is_active = data.get('role_id'), data.get('is_active')
    if type(role_id) is not int or not 1 <= role_id <= 9223372036854775807 or type(is_active) is not bool:
        invalid_input()
    return display_name, role_id, is_active


def checked_password(data, user):
    password = data.get('password')
    if not isinstance(password, str) or not password or len(password) > 512:
        invalid_input()
    try:
        validate_password(password, user)
    except ValidationError:
        raise APIError('invalid_input', 'رمز باید قوی، حداقل ۸ نویسه و متفاوت از نام کاربری باشد.', 422) from None
    return password


def replace_membership(user, role, membership=None):
    user.groups.set([role.group_id])
    user.user_permissions.clear()
    if membership is None:
        return StaffMembership.objects.create(user=user, role=role, revision=1)
    membership.role, membership.revision = role, membership.revision + 1
    membership.save(update_fields=['role', 'revision'])
    return membership


@transaction.atomic
def create_employee(actor, data):
    owner_required(actor)
    strict_fields(data, ('username', 'display_name', 'password', 'role_id', 'is_active'))
    display_name, role_id, is_active = employee_values(data)
    user_model = get_user_model()
    username = data.get('username')
    if not isinstance(username, str) or not username or len(username) > 150:
        invalid_input()
    try:
        user_model._meta.get_field('username').clean(username, None)
    except ValidationError:
        invalid_input()
    user = user_model(username=username, first_name=display_name, is_staff=True, is_active=is_active, is_superuser=False)
    password = checked_password(data, user)
    role = StaffRole.objects.select_for_update().get(pk=role_id)
    user.set_password(password)
    try:
        with transaction.atomic():
            user.save()
    except IntegrityError:
        raise APIError('duplicate_username', 'این نام کاربری قبلاً ثبت شده است.', 409) from None
    user.groups.set([role.group_id])
    StaffMembership.objects.create(user=user, role=role)
    audit(actor, 'staff_employee_created', user.pk, {}, {'role_id': role.pk, 'is_active': is_active})
    return employee_data(user)


@transaction.atomic
def update_employee(actor, user_id, data):
    owner_required(actor)
    strict_fields(data, ('display_name', 'role_id', 'is_active', 'revision'), ('password',))
    revision = revision_value(data)
    display_name, role_id, is_active = employee_values(data)
    role = StaffRole.objects.select_for_update().get(pk=role_id)
    # Lock the user even before a legacy membership exists, serializing its first assignment.
    user = get_user_model().objects.select_for_update().get(pk=user_id, is_staff=True)
    if user.is_superuser:
        raise APIError('owner_protected', 'حساب مدیر اصلی از این بخش قابل تغییر نیست.', 403)
    membership = StaffMembership.objects.select_for_update().filter(user=user).first()
    check_revision(revision, membership.revision if membership else 0)
    before = {'role_id': membership.role_id if membership else None, 'is_active': user.is_active}
    user.first_name, user.last_name, user.is_active = display_name, '', is_active
    fields = ['first_name', 'last_name', 'is_active']
    if 'password' in data:
        user.set_password(checked_password(data, user))
        fields.append('password')
    user.save(update_fields=fields)
    replace_membership(user, role, membership)
    audit(actor, 'staff_employee_updated', user.pk, before, {'role_id': role.pk, 'is_active': is_active})
    return employee_data(user)
