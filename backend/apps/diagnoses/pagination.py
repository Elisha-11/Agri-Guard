"""Cursor pagination for diagnosis history (contract `GET /diagnoses/`).

A cursor, not page numbers, because new diagnoses keep arriving while a phone pages through its history: page
numbers would shift and repeat or skip items. Responses are `{"next": url | null, "results": [...]}`.
"""

from rest_framework import exceptions
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response


class HistoryPagination(CursorPagination):
    page_size = 100
    ordering = ("-received_at", "-id")  # newest first; id breaks ties when a batch lands in the same instant

    def paginate_queryset(self, queryset, request, view=None):
        try:
            return super().paginate_queryset(queryset, request, view)
        except exceptions.NotFound as exc:  # DRF answers a bad cursor with 404; it's a bad parameter
            raise exceptions.ValidationError(
                {"cursor": ["Invalid cursor. Start again without one."]}
            ) from exc

    def get_paginated_response(self, data):
        return Response({"next": self.get_next_link(), "results": data})
