from django.urls import path
from api.views import (
    audit_log,
    bookings,
    channels,
    dashboard,
    demo_seed,
    expenses,
    guests,
    housekeeping,
    maintenance,
    marketing,
    messaging,
    notifications,
    payments,
    pricing_rules,
    reports,
    rooms,
    settings_view,
    staff,
    waitlist,
)

urlpatterns = [
    # Dashboard
    path("dashboard/stats", dashboard.DashboardStats.as_view()),

    # Rooms
    path("rooms", rooms.RoomList.as_view()),
    path("rooms/<str:room_id>", rooms.RoomDetail.as_view()),

    # Bookings
    path("bookings", bookings.BookingList.as_view()),
    path("bookings/<str:booking_id>", bookings.BookingDetail.as_view()),

    # Payments per booking
    path("bookings/<str:booking_id>/payments", payments.BookingPaymentList.as_view()),

    # Invoices
    path("invoices", payments.InvoiceList.as_view()),
    path("invoices/<str:invoice_id>", payments.InvoiceDetail.as_view()),

    # Guests
    path("guests", guests.GuestList.as_view()),
    path("guests/<str:guest_id>", guests.GuestDetail.as_view()),

    # Housekeeping
    path("housekeeping", housekeeping.HousekeepingList.as_view()),
    path("housekeeping/<str:room_id>", housekeeping.HousekeepingDetail.as_view()),

    # Pricing Rules
    path("pricing-rules", pricing_rules.PricingRuleList.as_view()),
    path("pricing-rules/<str:rule_id>", pricing_rules.PricingRuleDetail.as_view()),

    # Staff
    path("staff", staff.StaffList.as_view()),
    path("staff/<str:staff_id>", staff.StaffDetail.as_view()),

    # Maintenance
    path("maintenance", maintenance.MaintenanceList.as_view()),
    path("maintenance/<str:req_id>", maintenance.MaintenanceDetail.as_view()),

    # Expenses
    path("expenses", expenses.ExpenseList.as_view()),
    path("expenses/<str:expense_id>", expenses.ExpenseDetail.as_view()),

    # Reports
    path("reports/summary", reports.ReportsSummary.as_view()),
    path("reports/gst", reports.GSTReport.as_view()),
    path("reports/export/bookings", reports.ExportBookings.as_view()),

    # Notifications
    path("notifications", notifications.NotificationList.as_view()),
    path("notifications/<str:notification_id>/read", notifications.NotificationMarkRead.as_view()),

    # Audit Log
    path("audit-logs", audit_log.AuditLogList.as_view()),

    # Waitlist (admin)
    path("waitlist", waitlist.WaitlistList.as_view()),
    path("waitlist/<str:waitlist_id>", waitlist.WaitlistDetail.as_view()),

    # Settings
    path("settings", settings_view.SettingsView.as_view()),
    path("settings/domain/verify", settings_view.DomainVerificationView.as_view()),
    path("settings/room-categories", settings_view.RoomCategoriesView.as_view()),

    # Messaging
    path("messaging", messaging.MessagingDashboard.as_view()),
    path("messaging/templates", messaging.MessageTemplateList.as_view()),
    path("messaging/templates/<str:template_id>", messaging.MessageTemplateDetail.as_view()),
    path("messaging/send", messaging.MessagingSendView.as_view()),

    # Marketing
    path("marketing", marketing.MarketingDashboard.as_view()),
    path("marketing/contacts", marketing.MarketingContactList.as_view()),
    path("marketing/segments", marketing.MarketingSegmentList.as_view()),
    path("marketing/segments/<str:segment_id>", marketing.MarketingSegmentDetail.as_view()),
    path("marketing/campaigns", marketing.CampaignList.as_view()),
    path("marketing/campaigns/<str:campaign_id>", marketing.CampaignDetail.as_view()),
    path("marketing/campaigns/<str:campaign_id>/launch", marketing.CampaignLaunch.as_view()),

    # Channel Manager
    path("channels", channels.ChannelList.as_view()),
    path("channels/<str:channel_id>", channels.ChannelDetail.as_view()),
    path("channels/<str:channel_id>/sync", channels.ChannelSync.as_view()),

    # Demo seed
    path("demo/seed", demo_seed.DemoSeedView.as_view()),
]
