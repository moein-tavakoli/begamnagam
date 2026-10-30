from .management_api import staff_api
from .message_examples import MODELS, record_data, write_record
from .moderation import CATEGORIES
from .views import body


@staff_api(['GET'], 'core.manage_message_examples')
def catalog(request):
    return {**{kind: [record_data(kind, item) for item in model.objects.all()] for kind, model in MODELS.items()},
        'topics': [{'id': c['id'], 'label': c['label']} for c in CATEGORIES]}


@staff_api(['POST'], 'core.manage_message_examples')
def save(request, kind, record_id=None):
    return write_record(request.user, kind, body(request), record_id)


@staff_api(['POST'], 'core.manage_message_examples')
def delete(request, kind, record_id):
    return write_record(request.user, kind, body(request), record_id, delete=True)
