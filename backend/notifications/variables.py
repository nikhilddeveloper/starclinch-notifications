import re
from rest_framework.exceptions import ValidationError

PLACEHOLDER = re.compile(r'{{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*}}')
SOURCES = {'user.name', 'user.email', 'event.name', 'event.time'}
SAMPLES = {'user.name': 'Nikhil', 'user.email': 'nikhil@example.com', 'event.name': 'Login', 'event.time': '2026-09-30 12:00 UTC'}

def names(text):
    return list(dict.fromkeys(PLACEHOLDER.findall(text)))

def validate_content(title, body, mappings, channel):
    if not isinstance(mappings, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mappings.items()):
        raise ValidationError({'variable_mappings': 'Use a JSON object mapping variable names to supported sources.'})
    if any(v not in SOURCES for v in mappings.values()):
        raise ValidationError({'variable_mappings': 'Sources: ' + ', '.join(sorted(SOURCES))})
    for text in [title, body]:
        stripped = PLACEHOLDER.sub('', text)
        if '{{' in stripped or '}}' in stripped:
            raise ValidationError({'body': 'Use named placeholders such as {{name}}.'})
    missing = set(names(title + ' ' + body)) - set(mappings)
    if missing:
        raise ValidationError({'variable_mappings': 'Missing mappings: ' + ', '.join(sorted(missing))})
    if channel in ['email', 'push'] and not title.strip():
        raise ValidationError({'title': 'Email subject / push title is required.'})
    if channel == 'whatsapp' and len(body) > 1024:
        raise ValidationError({'body': 'WhatsApp body must be at most 1024 characters.'})
    if channel == 'push' and len(body) > 250:
        raise ValidationError({'body': 'Web Push body must be at most 250 characters.'})

def render(text, mappings, context):
    return PLACEHOLDER.sub(lambda m: str(context[mappings[m.group(1)]]), text)

def whatsapp_body(body):
    variables = names(body)
    return PLACEHOLDER.sub(lambda m: '{{' + str(variables.index(m.group(1)) + 1) + '}}', body)
