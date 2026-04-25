import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { Search, CalendarDays, MapPin, Phone, Mail } from "lucide-react";

interface Booking {
  id: string; guest_name: string; guest_email: string;
  check_in: string; check_out: string; guests: number;
  status: string; payment_status: string;
  total_amount: number; amount_paid: number;
  base_amount: number; tax_amount: number; service_charge: number;
  notes: string; created_at: string;
  room_name: string; check_in_time: string; check_out_time: string;
  cancellation_policy: string;
  property_name: string; contact_email: string; contact_phone: string;
  address: string; currency: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-green-100 text-green-800",
  cancelled: "bg-red-100 text-red-800",
  completed: "bg-blue-100 text-blue-800",
};

const PAY_COLORS: Record<string, string> = {
  unpaid: "bg-red-100 text-red-800",
  partial: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
};

const fmt = (iso: string) => {
  try { return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }); }
  catch { return iso; }
};

const GuestPortal = () => {
  const [email, setEmail] = useState("");
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!email.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.publicGet<{ bookings: Booking[] }>(`/public/booking-lookup?email=${encodeURIComponent(email.trim())}`);
      setBookings(res.bookings || []);
      setSearched(true);
    } catch (err: any) {
      setError("No bookings found for this email address.");
      setBookings([]);
      setSearched(true);
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex flex-col">
      <div className="flex-1 max-w-3xl mx-auto w-full px-4 py-12 space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">My Bookings</h1>
          <p className="text-muted-foreground mt-2">Look up your reservation by email address</p>
        </div>

        {/* Search Card */}
        <Card>
          <CardContent className="p-6">
            <div className="flex gap-3">
              <div className="flex-1 space-y-2">
                <Label>Email Address</Label>
                <Input
                  type="email"
                  placeholder="Enter the email you used when booking"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleSearch()}
                />
              </div>
              <div className="flex items-end">
                <Button onClick={handleSearch} disabled={loading || !email.trim()}>
                  <Search className="w-4 h-4 mr-2" />{loading ? "Searching..." : "Find Booking"}
                </Button>
              </div>
            </div>
            {error && <p className="text-destructive text-sm mt-3">{error}</p>}
          </CardContent>
        </Card>

        {/* Results */}
        {searched && bookings.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">{bookings.length} reservation{bookings.length > 1 ? "s" : ""} found</h2>
            {bookings.map(b => (
              <Card key={b.id} className="overflow-hidden">
                <div className="border-b px-6 py-4 flex items-center justify-between bg-muted/30">
                  <div>
                    <p className="font-semibold text-lg">{b.property_name}</p>
                    <p className="text-sm text-muted-foreground flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5" />{b.address}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${STATUS_COLORS[b.status] || ""}`}>{b.status}</span>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${PAY_COLORS[b.payment_status] || ""}`}>{b.payment_status}</span>
                  </div>
                </div>
                <CardContent className="p-6 space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Room</p>
                      <p className="font-medium">{b.room_name || "—"}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Guests</p>
                      <p className="font-medium">{b.guests} guest{b.guests > 1 ? "s" : ""}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Check-in</p>
                      <p className="font-medium">{fmt(b.check_in)}</p>
                      {b.check_in_time && <p className="text-xs text-muted-foreground">from {b.check_in_time}</p>}
                    </div>
                    <div>
                      <p className="text-muted-foreground">Check-out</p>
                      <p className="font-medium">{fmt(b.check_out)}</p>
                      {b.check_out_time && <p className="text-xs text-muted-foreground">by {b.check_out_time}</p>}
                    </div>
                  </div>
                  <Separator />
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Room charges</p>
                      <p className="font-medium">{formatCurrency(b.base_amount)}</p>
                    </div>
                    {b.tax_amount > 0 && (
                      <div><p className="text-muted-foreground">Taxes & GST</p><p className="font-medium">{formatCurrency(b.tax_amount)}</p></div>
                    )}
                    {b.service_charge > 0 && (
                      <div><p className="text-muted-foreground">Service charge</p><p className="font-medium">{formatCurrency(b.service_charge)}</p></div>
                    )}
                    <div>
                      <p className="text-muted-foreground">Total Amount</p>
                      <p className="text-lg font-bold">{formatCurrency(b.total_amount)}</p>
                    </div>
                    {b.amount_paid > 0 && (
                      <div>
                        <p className="text-muted-foreground">Amount Paid</p>
                        <p className="font-medium text-green-600">{formatCurrency(b.amount_paid)}</p>
                      </div>
                    )}
                    {b.total_amount - (b.amount_paid || 0) > 0 && b.payment_status !== "paid" && (
                      <div>
                        <p className="text-muted-foreground">Balance Due</p>
                        <p className="font-medium text-red-600">{formatCurrency(b.total_amount - (b.amount_paid || 0))}</p>
                      </div>
                    )}
                  </div>
                  {(b.contact_email || b.contact_phone) && (
                    <>
                      <Separator />
                      <div className="flex gap-6 text-sm">
                        {b.contact_email && (
                          <a href={`mailto:${b.contact_email}`} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground">
                            <Mail className="w-3.5 h-3.5" />{b.contact_email}
                          </a>
                        )}
                        {b.contact_phone && (
                          <a href={`tel:${b.contact_phone}`} className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground">
                            <Phone className="w-3.5 h-3.5" />{b.contact_phone}
                          </a>
                        )}
                      </div>
                    </>
                  )}
                  {b.cancellation_policy && (
                    <p className="text-xs text-muted-foreground bg-muted/50 rounded p-2">
                      Cancellation: {b.cancellation_policy}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">Booking ID: <span className="font-mono">{b.id.slice(0, 8).toUpperCase()}</span> · Booked on {fmt(b.created_at)}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default GuestPortal;
