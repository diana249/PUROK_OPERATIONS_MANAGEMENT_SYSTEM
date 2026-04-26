from rest_framework import permissions

from management.models import Resident


class IsStaffOrOwnResidentResource(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if isinstance(obj, Resident):
            return obj.user_id == request.user.id
        resident = getattr(obj, "resident", None)
        return resident is not None and resident.user_id == request.user.id
