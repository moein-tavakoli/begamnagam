from . import support
from .management_api import staff_api
from .models import SupportConversation
from .services import api, limited
from .views import body


def before(request):
    value=request.GET.get('before')
    return int(value) if value is not None else None


@api(['GET'],authenticated=True)
def summary(request):
    limited('support-customer-read',str(request.user.pk),120,60)
    return support.customer_summary(request.user)


@api(['GET','POST'],authenticated=True)
def messages(request):
    if request.method=='POST':
        return support.send(request.user,body(request),request.headers.get('Idempotency-Key',''))
    limited('support-customer-read',str(request.user.pk),120,60)
    thread=SupportConversation.objects.filter(account__user=request.user).first()
    return support.page_messages(request.user,thread,before(request))


@api(['POST'],authenticated=True)
def read(request):
    limited('support-customer-read-marker',str(request.user.pk),60,60)
    return support.mark_read(request.user,body(request))


@staff_api(['GET'])
def staff_summary(request):
    limited('support-staff-read',str(request.user.pk),120,60)
    return support.staff_summary(request.user)


@staff_api(['POST'])
def inbox(request):
    limited('support-staff-read',str(request.user.pk),120,60)
    return support.inbox(request.user,body(request))


@staff_api(['GET','POST'])
def staff_messages(request,thread_id):
    if request.method=='POST':
        return support.send(request.user,body(request),request.headers.get('Idempotency-Key',''),thread_id=thread_id,staff=True)
    limited('support-staff-read',str(request.user.pk),120,60)
    thread=support.conversation_for_staff(request.user,thread_id)
    return support.page_messages(request.user,thread,before(request),staff=True)


@staff_api(['POST'])
def staff_read(request,thread_id):
    return support.mark_read(request.user,body(request),thread_id=thread_id,staff=True)


@staff_api(['POST'])
def close(request,thread_id):
    return support.close(request.user,thread_id,body(request))
