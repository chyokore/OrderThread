"""Bounded Baseten transport for the public demo."""

import json
import urllib.request

from public_ai_budget import BudgetUnavailable


def guarded_completion(app, budget, model, key):
    def complete(messages, provider=None):
        if provider not in (None, 'baseten'):
            raise ValueError('This demo uses Baseten.')
        payload = json.dumps({
            'model': model, 'messages': messages, 'max_tokens': 2048,
            'temperature': 0, 'stream': False,
        }).encode('utf-8')
        if len(payload) > 2 * 1024 * 1024:
            raise ValueError('Use a smaller synthetic sample.')
        try:
            allowed = budget.reserve()
        except BudgetUnavailable as error:
            raise app.ProviderError(str(error)) from None
        if not allowed:
            raise app.ProviderError('The shared live AI allowance is exhausted.')
        request = urllib.request.Request(
            'https://inference.baseten.co/v1/chat/completions', data=payload,
            headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                result = json.loads(response.read(131072))
            if not isinstance(result, dict):
                raise ValueError('Unexpected Baseten response.')
        except (OSError, ValueError):
            raise app.ProviderError('Baseten request failed. No retry was made.') from None
        return result, {'provider': 'baseten', 'model': model}

    return complete
