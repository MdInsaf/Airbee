"""Role-based access control for Airbee API."""

from rest_framework.permissions import BasePermission
from django.db import connection


class AirbeePermission(BasePermission):
    """Base permission class with role checking."""

    required_role = None  # Override in subclasses

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if not self.required_role:
            return True

        return request.user.role in self.required_role


class IsOwner(AirbeePermission):
    """Only tenant owner can access."""
    required_role = ["owner"]


class IsManager(AirbeePermission):
    """Tenant owner or manager."""
    required_role = ["owner", "manager"]


class IsStaff(AirbeePermission):
    """Owner, manager, or staff."""
    required_role = ["owner", "manager", "staff"]


class IsStaffOrGuest(AirbeePermission):
    """Owner, manager, staff, or guest."""
    required_role = ["owner", "manager", "staff", "guest"]


class CanManageBookings(AirbeePermission):
    """Can view and manage bookings (staff+)."""
    required_role = ["owner", "manager", "staff"]


class CanManagePayments(AirbeePermission):
    """Can view and process payments (manager+)."""
    required_role = ["owner", "manager"]


class CanManageSettings(AirbeePermission):
    """Can view and modify tenant settings (owner only)."""
    required_role = ["owner"]


class CanManageStaff(AirbeePermission):
    """Can manage staff and roles (manager+)."""
    required_role = ["owner", "manager"]
