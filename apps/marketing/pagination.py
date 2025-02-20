from rest_framework.pagination import LimitOffsetPagination
from urllib.parse import urlencode
class CustomLimitOffsetPagination(LimitOffsetPagination):
    default_limit=10

    def get_next_link(self, request, offset, limit, total_count):
        next_offset = offset + limit
        if next_offset < total_count:
            absolute_uri = request.build_absolute_uri()
            if 'offset=' in absolute_uri and 'limit=' in absolute_uri:
                updated_uri = absolute_uri.replace(f'offset={offset}', f'offset={next_offset}', 1)
                return updated_uri
            query_params = urlencode({'offset': next_offset, 'limit': limit})
            return f'{request.build_absolute_uri()}&{query_params}'
        return None

    def get_previous_link(self, request, offset, limit):
        prev_offset = max(0, offset - limit)
        if prev_offset != offset:
            absolute_uri = request.build_absolute_uri()
            if 'offset=' in absolute_uri and 'limit=' in absolute_uri:
                updated_uri = absolute_uri.replace(f'offset={offset}', f'offset={prev_offset}', 1)
                return updated_uri
            query_params = urlencode({'offset': prev_offset, 'limit': limit})
            return f'{request.build_absolute_uri()}&{query_params}'
        return None