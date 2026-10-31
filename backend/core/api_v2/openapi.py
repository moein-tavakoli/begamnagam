"""Generate the specification from the same route/operation/request registry."""
import re

from .contracts import SCHEMAS, ref


def specification():
    from .urls import urlpatterns
    paths = {}
    for route in urlpatterns:
        operations = getattr(route.callback, 'api_operations', None)
        if operations is None:
            continue
        pattern = str(route.pattern)
        path = '/' + re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', pattern)
        paths[path] = {}
        for method, spec in operations.items():
            parameters = [{'name': name, 'in': 'path', 'required': True,
                           'schema': {'type': 'integer', 'minimum': 1} if converter == 'int'
                           else {'type': 'string', 'format': 'uuid'}}
                          for converter, name in re.findall(r'<(\w+):(\w+)>', pattern)]
            parameters += [{'name': name, 'in': 'query', 'schema': schema} for name, schema in spec['query'].items()]
            if spec['key']:
                parameters.append({'name': 'Idempotency-Key', 'in': 'header', 'required': True,
                                   'schema': {'type': 'string', 'format': 'uuid'},
                                   'description': 'Store a UUID per explicit user action. Reuse it with the exact same input on network retries.'})
            unsafe = method not in {'get', 'head', 'options'}
            if not spec['bot']:
                parameters.append({'name': 'X-Bot-Key', 'in': 'header', 'required': False,
                                   'schema': {'type': 'string'},
                                   'description': 'Required only when using a bot-owned session. Server-side adapter secret; ordinary web sessions omit it.'})
            if unsafe:
                parameters.append({'name': 'X-CSRFToken', 'in': 'header', 'required': True,
                                   'schema': {'type': 'string'}, 'description': 'Current session.csrf_token; refresh after login/logout.'})
            responses = {str(spec['status']): {'description': 'Success. Idempotent operations return the existing resource on replay.',
                                              'content': {'application/json': {'schema': ref(spec['response'])}}}}
            for code, label in {400: 'Malformed JSON or invalid phone', 401: 'Phone verification or valid bot credential required',
                                403: 'CSRF, recent authentication or permission required', 404: 'Missing or not owned',
                                405: 'Unsupported method', 409: 'Conflict, stale conversation/revision/event/preview, insufficient credit or disabled capability',
                                413: 'Body exceeds 8192 bytes', 415: 'application/json required',
                                422: 'Invalid fields, cursor, consent or content', 429: 'Rate or account limit',
                                503: 'Service or provider unavailable; do not assume success'}.items():
                responses[str(code)] = {'description': label, 'content': {'application/json': {'schema': ref('Error')}}}
            security = {'SessionCookie': []} if spec['auth'] else {}
            if spec['bot']:
                security['BotKey'] = []
                if spec['identifier'] not in {'resolveBotConversation', 'listBotConversations'}:
                    security['SessionCookie'] = []
            if unsafe:
                security['CSRFToken'] = []
            value = {'operationId': spec['identifier'], 'tags': [spec['tag']], 'summary': spec['summary'],
                     'description': spec['description'], 'parameters': parameters, 'responses': responses,
                     'security': [security] if security else []}
            if spec['request']:
                value['requestBody'] = {'required': True, 'content': {'application/json': {'schema': ref(spec['request'])}}}
            paths[path][method] = value
    return {'openapi': '3.0.3', 'info': {'title': 'BegamNagam integration API', 'version': '2.1.0',
            'description': 'REST API for the frontend, Telegram and Bale adapters. One verified phone account and isolated cookie jar per messenger user. '
                           'All mutations require CSRF. No messenger id, contact, admin session or API documentation permission replaces phone verification. '
                           'Trusted bot adapters can persist/resume isolated sessions and encrypted conversation stages. '
                           'Every request using a bot-owned session additionally requires its X-Bot-Key. '
                           'Integer toman amounts; wallet balances are decimal strings to preserve precision. '
                           'See /api/v2/document/guide for the Persian integration walkthrough. '
                           'The specification version is independent of the project release version.'},
            'servers': [{'url': '/api/v2', 'description': 'Same-origin API'}],
            'tags': [{'name': name} for name in ['Authentication', 'Catalog', 'Account', 'Messages', 'Credits and payments',
                                                'Invitations', 'Support', 'Recipient controls', 'Bot conversations']],
            'paths': paths, 'components': {'schemas': SCHEMAS, 'securitySchemes': {
                'SessionCookie': {'type': 'apiKey', 'in': 'cookie', 'name': 'sessionid',
                                  'description': 'HttpOnly Django session. Obtain by verifying OTP, not by sending a messenger user id.'},
                'BotKey': {'type': 'apiKey', 'in': 'header', 'name': 'X-Bot-Key',
                           'description': 'Private adapter credential, issued by manage_bot_integration. Different from the vendor bot token. '
                                          'Required on every request using a bot-owned session; never expose in a browser, URL or chat.'},
                'CSRFToken': {'type': 'apiKey', 'in': 'header', 'name': 'X-CSRFToken',
                              'description': 'From GET /session or /bootstrap; use the new value returned after POST /auth/sessions.'}}}}
