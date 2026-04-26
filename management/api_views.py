from datetime import date

from django.db.models import Q
from rest_framework import mixins, pagination, permissions, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from management.api_permissions import IsStaffOrOwnResidentResource
from management.api_serializers import (
    AttendanceSerializer,
    ClearanceSerializer,
    DashboardSummarySerializer,
    FeeSerializer,
    ResidentSerializer,
)
from management.models import Attendance, Fee, PurokClearance, Resident
from management.services.dashboard_service import build_dashboard_context


class StandardResultsSetPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _parse_iso_date(date_string):
    if not date_string:
        return None
    try:
        return date.fromisoformat(date_string)
    except ValueError:
        return None


class ResidentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ResidentSerializer
    permission_classes = [IsStaffOrOwnResidentResource]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Resident.objects.select_related("purok", "user").order_by("last_name", "first_name")
        search_query = (self.request.query_params.get("q") or "").strip()
        purok_id = (self.request.query_params.get("purok_id") or "").strip()
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query)
            )
        if purok_id.isdigit():
            queryset = queryset.filter(purok_id=int(purok_id))
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)


class AttendanceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AttendanceSerializer
    permission_classes = [IsStaffOrOwnResidentResource]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Attendance.objects.select_related("resident", "resident__user").order_by("-date", "-id")
        status = (self.request.query_params.get("status") or "").strip()
        attendance_type = (self.request.query_params.get("attendance_type") or "").strip()
        date_from = _parse_iso_date((self.request.query_params.get("date_from") or "").strip())
        date_to = _parse_iso_date((self.request.query_params.get("date_to") or "").strip())
        if status:
            queryset = queryset.filter(status=status)
        if attendance_type:
            queryset = queryset.filter(attendance_type=attendance_type)
        if date_from is not None:
            queryset = queryset.filter(date__gte=date_from)
        if date_to is not None:
            queryset = queryset.filter(date__lte=date_to)
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(resident__user=self.request.user)


class FeeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = FeeSerializer
    permission_classes = [IsStaffOrOwnResidentResource]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Fee.objects.select_related("resident", "resident__user", "fee_type").order_by("-id")
        paid = (self.request.query_params.get("paid") or "").strip().lower()
        fee_type_id = (self.request.query_params.get("fee_type_id") or "").strip()
        if paid in {"true", "1", "yes"}:
            queryset = queryset.filter(paid=True)
        elif paid in {"false", "0", "no"}:
            queryset = queryset.filter(paid=False)
        if fee_type_id.isdigit():
            queryset = queryset.filter(fee_type_id=int(fee_type_id))
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(resident__user=self.request.user)


class ClearanceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ClearanceSerializer
    permission_classes = [IsStaffOrOwnResidentResource]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = PurokClearance.objects.select_related("resident", "resident__user", "clearance_type").order_by("-date_issued", "-id")
        date_from = _parse_iso_date((self.request.query_params.get("date_from") or "").strip())
        date_to = _parse_iso_date((self.request.query_params.get("date_to") or "").strip())
        clearance_type_id = (self.request.query_params.get("clearance_type_id") or "").strip()
        if date_from is not None:
            queryset = queryset.filter(date_issued__gte=date_from)
        if date_to is not None:
            queryset = queryset.filter(date_issued__lte=date_to)
        if clearance_type_id.isdigit():
            queryset = queryset.filter(clearance_type_id=int(clearance_type_id))
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(resident__user=self.request.user)


class DashboardSummaryAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        context = build_dashboard_context(request.user)
        payload = {
            "total_residents": context["total_residents"],
            "total_attendance": context["total_attendance"],
            "unpaid_fees": context["unpaid_fees"],
            "clearances_issued": context["clearances_issued"],
        }
        return Response(DashboardSummarySerializer(payload).data)
