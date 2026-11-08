"""Strict owner-only endpoints, independent from product phone authentication."""
import re

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.views.decorators.vary import vary_on_cookie

from .input_digits import ascii_digits
from .management_api import staff_api
from .models import StaffRole
from . import staff_roles as roles
from .views import body


def pagination(request):
    if set(request.GET) - {'page', 'page_size', 'query'} or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
        roles.invalid_input()
    numbers = []
    for key, default, maximum in (('page', '1', 100000), ('page_size', '25', 100)):
        raw = ascii_digits(request.GET.get(key, default))
        if len(raw) > 6 or not re.fullmatch(r'[0-9]+', raw) or not 1 <= int(raw) <= maximum:
            roles.invalid_input()
        numbers.append(int(raw))
    query = request.GET.get('query', '').strip()
    if len(query) > 100:
        roles.invalid_input()
    return *numbers, query


def page_data(rows, page, page_size, serializer):
    return {'rows': [serializer(r) for r in rows[(page-1)*page_size:page*page_size]],
        'total': rows.count(), 'page': page, 'page_size': page_size}


@vary_on_cookie
@staff_api(['GET'])
def catalog(request):
    roles.owner_required(request.user)
    return {'sections': list(roles.SECTION_CATALOG)}


@vary_on_cookie
@staff_api(['GET', 'POST'])
def role_list(request):
    roles.owner_required(request.user)
    if request.method == 'POST':
        return roles.create_role(request.user, body(request))
    page, page_size, query = pagination(request)
    rows = StaffRole.objects.filter(name__icontains=ascii_digits(query)).order_by('name', 'pk')
    return page_data(rows, page, page_size, roles.role_data)


@vary_on_cookie
@staff_api(['PATCH', 'DELETE'])
def role_detail(request, role_id):
    roles.owner_required(request.user)
    action = roles.delete_role if request.method == 'DELETE' else roles.update_role
    return action(request.user, role_id, body(request))


@vary_on_cookie
@staff_api(['GET', 'POST'])
def employee_list(request):
    roles.owner_required(request.user)
    if request.method == 'POST':
        return roles.create_employee(request.user, body(request))
    page, page_size, query = pagination(request)
    rows = get_user_model().objects.filter(is_staff=True)
    if query:
        name_query = ascii_digits(query)
        rows = rows.filter(Q(username__icontains=query) | Q(first_name__icontains=name_query) | Q(last_name__icontains=name_query))
    return page_data(rows.order_by('username', 'pk'), page, page_size, roles.employee_data)


@vary_on_cookie
@staff_api(['PATCH'])
def employee_detail(request, user_id):
    roles.owner_required(request.user)
    return roles.update_employee(request.user, user_id, body(request))
