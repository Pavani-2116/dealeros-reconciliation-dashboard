"""The single API endpoint: GET /api/disagreements/?org=ORG-A&reason=...&sort=..."""
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .compare import ALL_REASONS
from .services import disagreements_for_org, valid_orgs


def _error(message):
    return Response({'error': message}, status=400)


@api_view(['GET'])
def disagreements(request):
    org = request.query_params.get('org', '').strip()
    reason = request.query_params.get('reason', '').strip() or None
    sort = request.query_params.get('sort', '').strip() or None

    if not org:
        return _error('The "org" query parameter is required, e.g. ?org=ORG-A.')
    if org not in valid_orgs():
        return _error(f'Unknown org {org!r}. Valid orgs: {", ".join(valid_orgs())}.')
    if reason and reason not in ALL_REASONS:
        return _error(f'Unknown reason {reason!r}. Valid reasons: {", ".join(ALL_REASONS)}.')
    if sort and sort not in ('value', '-value'):
        return _error('"sort" must be "value" or "-value".')

    return Response(disagreements_for_org(org, reason=reason, sort=sort))
