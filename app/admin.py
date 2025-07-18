# app/admin.py

from sqladmin import ModelView
from .models import User, Alert, AdminReview, Warning, FeaturedItem


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.userid, User.is_admin, User.created_at]
    column_searchable_list = [User.email, User.userid]
    column_sortable_list = [User.created_at, User.is_admin]
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"


class AlertAdmin(ModelView, model=Alert):
    column_list = [Alert.id, Alert.status, Alert.type, Alert.user, Alert.created_at]
    column_details_exclude_list = [
        Alert.location
    ]  # Exclude raw location data from detail view
    column_filters = [Alert.status, Alert.type]
    name = "Alert"
    name_plural = "Alerts"
    icon = "fa-solid fa-triangle-exclamation"


class AdminReviewAdmin(ModelView, model=AdminReview):
    column_list = [
        AdminReview.alert_id,
        AdminReview.admin,
        AdminReview.vote,
        AdminReview.created_at,
    ]
    name = "Admin Review"
    name_plural = "Admin Reviews"
    icon = "fa-solid fa-check-to-slot"


class WarningAdmin(ModelView, model=Warning):
    column_list = [
        Warning.id,
        Warning.user,
        Warning.reason,
        Warning.issuer,
        Warning.created_at,
    ]
    name = "Warning"
    name_plural = "Warnings"
    icon = "fa-solid fa-gavel"


class FeaturedItemAdmin(ModelView, model=FeaturedItem):
    column_list = [
        FeaturedItem.id,
        FeaturedItem.title,
        FeaturedItem.user,
        FeaturedItem.created_at,
        FeaturedItem.expires_at,
    ]
    name = "Featured Item"
    name_plural = "Featured Items"
    icon = "fa-solid fa-star"
