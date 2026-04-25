import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface Room { id: string; name: string; }
interface Booking {
  id: string; room_id: string; guest_name: string;
  check_in: string; check_out: string; status: string;
}

const STATUS_COLORS: Record<string, string> = {
  confirmed: "bg-green-500/80 text-white",
  pending: "bg-yellow-400/80 text-black",
  completed: "bg-blue-400/80 text-white",
  cancelled: "bg-red-400/40 text-red-900 line-through",
};

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

const BookingCalendar = () => {
  const { tenantId } = useAuth();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  useEffect(() => {
    if (!tenantId) return;
    Promise.all([api.get<any[]>("/api/rooms"), api.get<any[]>("/api/bookings")])
      .then(([r, b]) => { setRooms(r || []); setBookings(b || []); })
      .finally(() => setLoading(false));
  }, [tenantId]);

  const daysInMonth = getDaysInMonth(year, month);
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const monthName = new Date(year, month, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

  const prevMonth = () => {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
  };

  const getCellBooking = (roomId: string, day: number) => {
    const cellDate = new Date(year, month, day);
    return bookings.find(b => {
      if (b.room_id !== roomId) return false;
      const ci = new Date(b.check_in);
      const co = new Date(b.check_out);
      return cellDate >= ci && cellDate < co;
    });
  };

  const isCheckIn = (booking: Booking, day: number) => {
    const ci = new Date(booking.check_in);
    return ci.getFullYear() === year && ci.getMonth() === month && ci.getDate() === day;
  };

  const today = new Date();
  const isToday = (day: number) =>
    today.getFullYear() === year && today.getMonth() === month && today.getDate() === day;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Booking Calendar</h1>
        <p className="text-muted-foreground mt-1">Room availability at a glance</p>
      </div>

      <div className="flex items-center gap-3">
        <Button variant="outline" size="icon" onClick={prevMonth}><ChevronLeft className="w-4 h-4" /></Button>
        <span className="text-lg font-semibold w-44 text-center">{monthName}</span>
        <Button variant="outline" size="icon" onClick={nextMonth}><ChevronRight className="w-4 h-4" /></Button>
        <div className="ml-4 flex gap-3 text-xs text-muted-foreground">
          {Object.entries(STATUS_COLORS).map(([s, cls]) => (
            <span key={s} className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{s}</span>
          ))}
        </div>
      </div>

      {loading ? (
        <Card><CardContent className="p-6"><div className="h-64 bg-muted rounded animate-pulse" /></CardContent></Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="min-w-full text-xs border-collapse">
              <thead>
                <tr>
                  <th className="sticky left-0 z-10 bg-background border border-border px-3 py-2 text-left font-semibold min-w-[120px]">
                    Room
                  </th>
                  {days.map(d => (
                    <th key={d} className={`border border-border px-1 py-2 text-center font-medium min-w-[32px] ${isToday(d) ? "bg-primary/10 text-primary" : ""}`}>
                      {d}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rooms.map(room => (
                  <tr key={room.id} className="hover:bg-muted/30">
                    <td className="sticky left-0 z-10 bg-background border border-border px-3 py-2 font-medium truncate max-w-[120px]">
                      {room.name}
                    </td>
                    {days.map(d => {
                      const booking = getCellBooking(room.id, d);
                      const showLabel = booking && isCheckIn(booking, d);
                      return (
                        <td key={d} className={`border border-border px-0 py-0 h-8 relative ${isToday(d) ? "bg-primary/5" : ""}`}>
                          {booking ? (
                            <div
                              title={`${booking.guest_name} (${booking.check_in} → ${booking.check_out})`}
                              className={`h-full w-full flex items-center px-1 text-[10px] truncate cursor-pointer ${STATUS_COLORS[booking.status] || "bg-gray-300"}`}
                            >
                              {showLabel ? booking.guest_name : ""}
                            </div>
                          ) : null}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {rooms.length === 0 && (
                  <tr><td colSpan={daysInMonth + 1} className="text-center py-8 text-muted-foreground">No rooms found</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};

export default BookingCalendar;
