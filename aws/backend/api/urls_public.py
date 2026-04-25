from django.urls import path

from api.views.public_booking import (
    PublicBookingCreateView,
    PublicPropertyView,
    PublicSiteBookingCreateView,
    PublicSiteView,
    PublicBookingLookup,
)
from api.views.channels import ChannelICalExport
from api.views.waitlist import PublicWaitlistCreate

urlpatterns = [
    path("site", PublicSiteView.as_view()),
    path("site/bookings", PublicSiteBookingCreateView.as_view()),
    path("properties/<slug:property_slug>", PublicPropertyView.as_view()),
    path("properties/<slug:property_slug>/bookings", PublicBookingCreateView.as_view()),
    path("ical/<slug:tenant_slug>/<str:room_id>.ics", ChannelICalExport.as_view()),
    path("booking-lookup", PublicBookingLookup.as_view()),
    path("waitlist", PublicWaitlistCreate.as_view()),
]
