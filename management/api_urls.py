from django.urls import include, path
from rest_framework.routers import DefaultRouter

from management.api_views import AttendanceViewSet, ClearanceViewSet, DashboardSummaryAPIView, FeeViewSet, ResidentViewSet

router = DefaultRouter()
router.register("residents", ResidentViewSet, basename="api-residents")
router.register("attendance", AttendanceViewSet, basename="api-attendance")
router.register("fees", FeeViewSet, basename="api-fees")
router.register("clearances", ClearanceViewSet, basename="api-clearances")

urlpatterns = [
    path("dashboard/", DashboardSummaryAPIView.as_view(), name="api-dashboard-summary"),
    path("", include(router.urls)),
]
