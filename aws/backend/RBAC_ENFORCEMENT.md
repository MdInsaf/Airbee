# RBAC Enforcement: Which Endpoints Need What Permissions

## Endpoint Permission Matrix

### Public/Guest Accessible (No Auth Required)
- `POST /public/site/bookings` — Public booking creation
- `POST /public/bookings/<id>/cancel` — Guest cancellation via token
- `GET /public/properties/<slug>` — Public property view
- `GET /public/ical/<feed_token>.ics` — iCal feed

### Authenticated (Any Role)
- `GET /api/rooms` — View available rooms
- `GET /api/bookings` — View own tenant's bookings (filtered server-side)
- `POST /ai/*` — Use AI features (all roles can ask questions)
- `GET /health/*` — Health checks

### Staff+  (staff, manager, owner)
- `POST /api/bookings` — Create booking
- `PUT /api/bookings/<id>` — Update booking status
- `GET /api/bookings/<id>/payments` — View booking payments
- `POST /api/bookings/<id>/payments` — Create payment record
- `GET /api/housekeeping` — View housekeeping tasks
- `PUT /api/housekeeping/<id>` — Update cleaning status

### Manager+ (manager, owner)
- `PUT /api/payments/<id>` — Refund payment
- `DELETE /api/bookings/<id>` — Cancel booking
- `POST /api/bookings/bulk` — Bulk booking operations
- `GET /api/staff` — List staff
- `POST /api/staff` — Create staff account
- `PUT /api/staff/<id>` — Update staff
- `DELETE /api/staff/<id>` — Remove staff

### Owner Only
- `GET /api/settings` — View settings
- `PUT /api/settings` — Modify settings
- `POST /api/settings/domain/verify` — Verify domain
- `DELETE /api/staff/<id>/role` — Modify staff roles
- `GET /api/payments` — View all payments (financial access)

---

## Implementation Priority

1. **Critical (P0):** Manager+ and Owner+ endpoints
   - `api/views/staff.py` — StaffManagementView
   - `api/views/settings_view.py` — SettingsView
   - `api/views/payments.py` — PaymentList, PaymentDetail

2. **High (P1):** Staff+ endpoints
   - `api/views/bookings.py` — BookingList, BookingDetail
   - `api/views/housekeeping.py` — HousekeepingView
   - `api/views/maintenance.py` — MaintenanceView

3. **Medium (P2):** Public/guest endpoints
   - `api/views/public_booking.py` — already requires minimal auth

---

## Example: Apply Permission to View

```python
from api.permissions import IsManager, CanManageStaff

class StaffManagementView(APIView):
    permission_classes = [IsManager]  # Only manager+
    
    def get(self, request):
        # List staff
        pass
    
    def post(self, request):
        # Create staff
        pass

class SettingsView(APIView):
    permission_classes = [IsOwner]  # Only owner
    
    def get(self, request):
        # View settings
        pass
```

---

## Testing RBAC

```python
def test_guest_cannot_access_staff_endpoint(self):
    self.client.force_authenticate(
        user=MagicMock(role="guest", tenant_id="...")
    )
    response = self.client.get("/api/staff")
    self.assertEqual(response.status_code, 403)

def test_manager_can_create_staff(self):
    self.client.force_authenticate(
        user=MagicMock(role="manager", tenant_id="...")
    )
    response = self.client.post("/api/staff", {...})
    self.assertEqual(response.status_code, 201)
```
