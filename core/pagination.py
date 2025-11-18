"""
Centralized pagination utilities for the Kita application.

This module provides reusable pagination helpers to standardize
pagination across the application.
"""
from __future__ import annotations
from typing import Optional, Dict, Any, TypeVar, Generic
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import QuerySet
from django.http import HttpRequest
from rest_framework.pagination import PageNumberPagination as DRFPageNumberPagination

T = TypeVar('T')


class StandardPaginator(Generic[T]):
    """
    Standard paginator for Django views.

    Provides consistent pagination with error handling.
    """

    DEFAULT_PAGE_SIZE = 25
    MAX_PAGE_SIZE = 100

    def __init__(
        self,
        queryset: QuerySet[T],
        page_size: Optional[int] = None,
        allow_empty_first_page: bool = True
    ):
        """
        Initialize paginator.

        Args:
            queryset: QuerySet to paginate
            page_size: Items per page
            allow_empty_first_page: Allow empty first page
        """
        self.queryset = queryset
        self.page_size = min(
            page_size or self.DEFAULT_PAGE_SIZE,
            self.MAX_PAGE_SIZE
        )
        self.paginator = Paginator(
            queryset,
            self.page_size,
            allow_empty_first_page=allow_empty_first_page
        )

    def get_page(self, request: HttpRequest) -> Dict[str, Any]:
        """
        Get paginated page from request.

        Args:
            request: HTTP request with page parameter

        Returns:
            Dictionary with page data and metadata
        """
        page_number = request.GET.get('page', 1)

        # Also check for 'p' parameter (common alternative)
        if not page_number:
            page_number = request.GET.get('p', 1)

        try:
            page = self.paginator.page(page_number)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page
            page = self.paginator.page(1)
        except EmptyPage:
            # If page is out of range, deliver last page
            page = self.paginator.page(self.paginator.num_pages)

        return self._build_response(page)

    def get_page_by_number(self, page_number: int) -> Dict[str, Any]:
        """
        Get specific page by number.

        Args:
            page_number: Page number

        Returns:
            Dictionary with page data and metadata
        """
        try:
            page = self.paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page = self.paginator.page(1)

        return self._build_response(page)

    def _build_response(self, page) -> Dict[str, Any]:
        """
        Build standardized pagination response.

        Args:
            page: Django Page object

        Returns:
            Dictionary with pagination data
        """
        return {
            'items': list(page.object_list),
            'page': page.number,
            'total_pages': self.paginator.num_pages,
            'total_items': self.paginator.count,
            'per_page': self.page_size,
            'has_next': page.has_next(),
            'has_previous': page.has_previous(),
            'next_page': page.next_page_number() if page.has_next() else None,
            'previous_page': page.previous_page_number() if page.has_previous() else None,
            'start_index': page.start_index(),
            'end_index': page.end_index(),
        }


class AjaxPaginator(StandardPaginator[T]):
    """
    Paginator optimized for AJAX requests.

    Returns JSON-friendly data structures.
    """

    def get_page_json(self, request: HttpRequest) -> Dict[str, Any]:
        """
        Get page data formatted for JSON response.

        Args:
            request: HTTP request

        Returns:
            JSON-serializable dictionary
        """
        page_data = self.get_page(request)

        # Convert items to dictionaries if they're model instances
        if page_data['items'] and hasattr(page_data['items'][0], '__dict__'):
            from django.forms.models import model_to_dict
            page_data['items'] = [
                model_to_dict(item) for item in page_data['items']
            ]

        return page_data


class CursorPaginator:
    """
    Cursor-based pagination for efficient large dataset navigation.

    Uses ID-based cursors instead of page numbers.
    """

    DEFAULT_PAGE_SIZE = 25

    def __init__(
        self,
        queryset: QuerySet,
        page_size: Optional[int] = None,
        ordering: str = '-id'
    ):
        """
        Initialize cursor paginator.

        Args:
            queryset: QuerySet to paginate
            page_size: Items per page
            ordering: Field to order by
        """
        self.queryset = queryset
        self.page_size = page_size or self.DEFAULT_PAGE_SIZE
        self.ordering = ordering

    def get_page(
        self,
        cursor: Optional[str] = None,
        direction: str = 'next'
    ) -> Dict[str, Any]:
        """
        Get page using cursor.

        Args:
            cursor: Cursor value (usually an ID)
            direction: 'next' or 'previous'

        Returns:
            Dictionary with items and navigation cursors
        """
        queryset = self.queryset.order_by(self.ordering)

        if cursor:
            if direction == 'next':
                if self.ordering.startswith('-'):
                    queryset = queryset.filter(id__lt=cursor)
                else:
                    queryset = queryset.filter(id__gt=cursor)
            else:  # previous
                if self.ordering.startswith('-'):
                    queryset = queryset.filter(id__gt=cursor)
                else:
                    queryset = queryset.filter(id__lt=cursor)
                queryset = queryset.reverse()

        items = list(queryset[:self.page_size + 1])
        has_more = len(items) > self.page_size

        if has_more:
            items = items[:self.page_size]

        next_cursor = None
        previous_cursor = None

        if items:
            if direction == 'next':
                next_cursor = str(items[-1].id) if has_more else None
                previous_cursor = str(items[0].id)
            else:
                previous_cursor = str(items[0].id) if has_more else None
                next_cursor = str(items[-1].id)
                items.reverse()  # Restore original order

        return {
            'items': items,
            'next_cursor': next_cursor,
            'previous_cursor': previous_cursor,
            'has_next': bool(next_cursor),
            'has_previous': bool(previous_cursor),
        }


class ApiPagination(DRFPageNumberPagination):
    """
    Standard pagination for Django REST Framework views.

    Provides consistent pagination for API endpoints.
    """

    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'

    def get_paginated_response(self, data):
        """
        Get paginated response with metadata.

        Args:
            data: Serialized page data

        Returns:
            Response with pagination metadata
        """
        from rest_framework.response import Response

        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'page_size': self.page.paginator.per_page,
            'results': data
        })


# Utility functions
def paginate_queryset(
    request: HttpRequest,
    queryset: QuerySet,
    page_size: int = 25
) -> Dict[str, Any]:
    """
    Convenience function to paginate a queryset.

    Args:
        request: HTTP request
        queryset: QuerySet to paginate
        page_size: Items per page

    Returns:
        Pagination data dictionary
    """
    paginator = StandardPaginator(queryset, page_size)
    return paginator.get_page(request)


def get_page_range(current_page: int, total_pages: int, window: int = 5) -> list[int]:
    """
    Get page range for pagination display.

    Args:
        current_page: Current page number
        total_pages: Total number of pages
        window: Number of pages to show around current

    Returns:
        List of page numbers to display
    """
    if total_pages <= window * 2 + 1:
        return list(range(1, total_pages + 1))

    if current_page <= window:
        return list(range(1, window * 2 + 2))

    if current_page >= total_pages - window:
        return list(range(total_pages - window * 2, total_pages + 1))

    return list(range(current_page - window, current_page + window + 1))


def build_pagination_context(
    page,
    base_url: str = '',
    extra_params: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Build context dictionary for pagination templates.

    Args:
        page: Django Page object
        base_url: Base URL for pagination links
        extra_params: Extra query parameters to preserve

    Returns:
        Context dictionary for templates
    """
    from urllib.parse import urlencode

    def build_url(page_num: int) -> str:
        params = {'page': page_num}
        if extra_params:
            params.update(extra_params)
        query_string = urlencode(params)
        return f"{base_url}?{query_string}" if base_url else f"?{query_string}"

    context = {
        'page': page,
        'paginator': page.paginator,
        'is_paginated': page.has_other_pages(),
        'page_range': get_page_range(
            page.number,
            page.paginator.num_pages
        ),
        'first_page_url': build_url(1),
        'last_page_url': build_url(page.paginator.num_pages),
    }

    if page.has_previous():
        context['previous_page_url'] = build_url(page.previous_page_number())

    if page.has_next():
        context['next_page_url'] = build_url(page.next_page_number())

    # Add numbered page URLs
    context['page_urls'] = {
        num: build_url(num) for num in context['page_range']
    }

    return context


class InfinitePaginator:
    """
    Paginator for infinite scroll implementations.
    """

    DEFAULT_PAGE_SIZE = 20

    def __init__(self, queryset: QuerySet, page_size: Optional[int] = None):
        """
        Initialize infinite scroll paginator.

        Args:
            queryset: QuerySet to paginate
            page_size: Items per batch
        """
        self.queryset = queryset
        self.page_size = page_size or self.DEFAULT_PAGE_SIZE

    def get_batch(
        self,
        last_id: Optional[int] = None,
        timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get next batch for infinite scroll.

        Args:
            last_id: ID of last item in previous batch
            timestamp: Timestamp for time-based pagination

        Returns:
            Batch data with continuation token
        """
        queryset = self.queryset

        if last_id:
            queryset = queryset.filter(id__gt=last_id)
        elif timestamp:
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(timestamp)
            if dt:
                queryset = queryset.filter(created_at__lt=dt)

        items = list(queryset[:self.page_size + 1])
        has_more = len(items) > self.page_size

        if has_more:
            items = items[:self.page_size]

        continuation_token = None
        if has_more and items:
            last_item = items[-1]
            continuation_token = str(last_item.id)
            if hasattr(last_item, 'created_at'):
                continuation_token = f"{last_item.id}:{last_item.created_at.isoformat()}"

        return {
            'items': items,
            'has_more': has_more,
            'continuation_token': continuation_token,
            'count': len(items)
        }


# Export commonly used classes
__all__ = [
    'StandardPaginator',
    'AjaxPaginator',
    'CursorPaginator',
    'ApiPagination',
    'InfinitePaginator',
    'paginate_queryset',
    'get_page_range',
    'build_pagination_context',
]