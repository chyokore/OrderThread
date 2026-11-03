"""Reserve one public inference attempt in D1 before contacting the provider."""

import json
import re
import urllib.request


class BudgetUnavailable(Exception):
    pass


class PublicAIBudget:
    def __init__(self, account_id, database_id, token):
        if not re.fullmatch(r'[0-9a-f]{32}', account_id):
            raise ValueError('Invalid D1 account ID.')
        if not re.fullmatch(r'[0-9a-f-]{36}', database_id) or not token.strip():
            raise ValueError('D1 database ID and token are required.')
        self.url = f'https://api.cloudflare.com/client/v4/accounts/{account_id}/d1/database/{database_id}/query'
        self.token = token

    def reserve(self):
        """Return False when exhausted. Errors deny inference and never trigger retries."""
        request = urllib.request.Request(
            self.url,
            data=json.dumps({
                'sql': 'UPDATE ai_budget SET remaining = remaining - 1 '
                       'WHERE id = 1 AND remaining > 0 RETURNING id',
            }).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read(16385))
            result, = payload['result']
            if payload['success'] is not True or result['success'] is not True:
                raise ValueError('D1 rejected reservation.')
            if result['results'] == [{'id': 1}]:
                return True
            if result['results'] == []:
                return False
        except (OSError, ValueError, KeyError, TypeError):
            raise BudgetUnavailable('Public AI is temporarily unavailable.') from None
        raise BudgetUnavailable('Public AI is temporarily unavailable.')
