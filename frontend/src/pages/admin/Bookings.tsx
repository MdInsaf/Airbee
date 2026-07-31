import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { formatCurrency, formatDate } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";
import { Plus, CalendarDays, Layers, ArrowRightLeft, X, Loader2 } from "lucide-react";

interface Booking {
  id: string;
  guest_name: string;
  guest_email: string | null;
  guest_phone: string | null;
  check_in: string;
  check_out: string;
  guests: number;
  total_amount: number;
  status: string;
  payment_status: string;
  amount_paid: number;
  room_id: string;
  rooms?: { name: string } | null;
}

interface Room {
  id: string;
  name: string;
  base_price: number;
}

const Bookings = () => {
  const { tenantId } = useAuth();
  const { toast } = useToast();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkSubmitting, setBulkSubmitting] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferBooking, setTransferBooking] = useState<Booking | null>(null);
  const [transferRoomId, setTransferRoomId] = useState<string>("");
  const [transferSubmitting, setTransferSubmitting] = useState(false);

  type BulkRow = {
    guest_name: string; guest_email: string; guest_phone: string;
    room_id: string; check_in: string; check_out: string;
    guests: number; total_amount: number;
  };
  const blankBulkRow = (): BulkRow => ({
    guest_name: "", guest_email: "", guest_phone: "",
    room_id: "", check_in: "", check_out: "", guests: 1, total_amount: 0,
  });
  const [bulkRows, setBulkRows] = useState<BulkRow[]>([blankBulkRow(), blankBulkRow(), blankBulkRow()]);

  const [form, setForm] = useState({
    guest_name: "", guest_email: "", guest_phone: "",
    room_id: "", check_in: "", check_out: "", guests: 1, total_amount: 0,
  });

  const fetchData = async () => {
    if (!tenantId) return;
    try {
      const [bookingsData, roomsData] = await Promise.all([
        api.get<any[]>("/api/bookings"),
        api.get<any[]>("/api/rooms"),
      ]);
      setBookings((bookingsData || []).map((b: any) => ({
        ...b,
        rooms: b.room_name ? { name: b.room_name } : null,
      })));
      setRooms((roomsData || []).filter((r: any) => r.status === "available"));
    } catch (err) {
      console.error("Bookings fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [tenantId]);

  const handlePaymentUpdate = async (bookingId: string, newPaymentStatus: string) => {
    try {
      await api.put(`/api/bookings/${bookingId}`, { payment_status: newPaymentStatus });
      setBookings(prev => prev.map(b => b.id === bookingId ? { ...b, payment_status: newPaymentStatus } : b));
      toast({ title: "Payment status updated" });
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  const handleStatusUpdate = async (bookingId: string, newStatus: string) => {
    try {
      await api.put(`/api/bookings/${bookingId}`, { status: newStatus });
      setBookings(prev => prev.map(b => b.id === bookingId ? { ...b, status: newStatus } : b));
      toast({ title: "Booking status updated" });
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  const handleCreate = async () => {
    if (!tenantId || !form.guest_name || !form.room_id || !form.check_in || !form.check_out) return;
    try {
      await api.post("/api/bookings", {
        guest_name: form.guest_name,
        guest_email: form.guest_email || null,
        guest_phone: form.guest_phone || null,
        room_id: form.room_id,
        check_in: form.check_in,
        check_out: form.check_out,
        guests: form.guests,
        total_amount: form.total_amount,
      });
      toast({ title: "Booking created" });
      setDialogOpen(false);
      setForm({ guest_name: "", guest_email: "", guest_phone: "", room_id: "", check_in: "", check_out: "", guests: 1, total_amount: 0 });
      fetchData();
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: "bg-[hsl(var(--warning))]/10 text-[hsl(var(--warning))] border-[hsl(var(--warning))]/30",
      confirmed: "bg-[hsl(var(--success))]/10 text-[hsl(var(--success))] border-[hsl(var(--success))]/30",
      cancelled: "bg-destructive/10 text-destructive border-destructive/30",
      completed: "bg-primary/10 text-primary border-primary/30",
    };
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${colors[status] || ""}`}>{status}</span>;
  };

  const paymentBadge = (status: string) => {
    const colors: Record<string, string> = {
      unpaid: "bg-destructive/10 text-destructive",
      partial: "bg-[hsl(var(--warning))]/10 text-[hsl(var(--warning))]",
      paid: "bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]",
    };
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || ""}`}>{status}</span>;
  };

  const updateBulkRow = (idx: number, patch: Partial<BulkRow>) => {
    setBulkRows(prev => prev.map((r, i) => {
      if (i !== idx) return r;
      const next = { ...r, ...patch };
      if ((patch.room_id || patch.check_in || patch.check_out) && next.room_id && next.check_in && next.check_out) {
        const room = rooms.find(rm => rm.id === next.room_id);
        if (room) {
          const nights = Math.max(1, Math.ceil((new Date(next.check_out).getTime() - new Date(next.check_in).getTime()) / 86400000));
          next.total_amount = Number(room.base_price) * nights;
        }
      }
      return next;
    }));
  };

  const handleBulkCreate = async () => {
    const valid = bulkRows.filter(r => r.guest_name && r.room_id && r.check_in && r.check_out);
    if (valid.length === 0) {
      toast({ title: "No valid rows", description: "Fill at least one row (guest, room, dates)", variant: "destructive" });
      return;
    }
    setBulkSubmitting(true);
    try {
      const res = await api.post<{ created: any[]; count: number }>("/api/bookings/bulk", {
        bookings: valid.map(r => ({
          guest_name: r.guest_name,
          guest_email: r.guest_email || null,
          guest_phone: r.guest_phone || null,
          room_id: r.room_id,
          check_in: r.check_in,
          check_out: r.check_out,
          guests: r.guests,
          total_amount: r.total_amount,
        })),
      });
      toast({ title: `Created ${res.count} bookings` });
      setBulkOpen(false);
      setBulkRows([blankBulkRow(), blankBulkRow(), blankBulkRow()]);
      fetchData();
    } catch (err: any) {
      toast({ title: "Bulk create failed", description: err.message, variant: "destructive" });
    } finally {
      setBulkSubmitting(false);
    }
  };

  const openTransfer = (b: Booking) => {
    setTransferBooking(b);
    setTransferRoomId("");
    setTransferOpen(true);
  };

  const handleTransfer = async () => {
    if (!transferBooking || !transferRoomId) return;
    setTransferSubmitting(true);
    try {
      await api.put(`/api/bookings/${transferBooking.id}`, { room_id: transferRoomId });
      toast({ title: "Room transferred" });
      setTransferOpen(false);
      setTransferBooking(null);
      fetchData();
    } catch (err: any) {
      toast({ title: "Transfer failed", description: err.message, variant: "destructive" });
    } finally {
      setTransferSubmitting(false);
    }
  };

  // Auto-calculate price
  useEffect(() => {
    if (form.room_id && form.check_in && form.check_out) {
      const room = rooms.find(r => r.id === form.room_id);
      if (room) {
        const nights = Math.max(1, Math.ceil((new Date(form.check_out).getTime() - new Date(form.check_in).getTime()) / 86400000));
        setForm(f => ({ ...f, total_amount: Number(room.base_price) * nights }));
      }
    }
  }, [form.room_id, form.check_in, form.check_out, rooms]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Bookings</h1>
          <p className="text-muted-foreground mt-1">Manage reservations</p>
        </div>
        <div className="flex items-center gap-2">
        <Button variant="outline" onClick={() => setBulkOpen(true)}>
          <Layers className="w-4 h-4 mr-2" />Bulk Booking
        </Button>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button><Plus className="w-4 h-4 mr-2" />New Booking</Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Create Booking</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Guest Name</Label>
                <Input value={form.guest_name} onChange={(e) => setForm(f => ({ ...f, guest_name: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input type="email" value={form.guest_email} onChange={(e) => setForm(f => ({ ...f, guest_email: e.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>Phone</Label>
                  <Input value={form.guest_phone} onChange={(e) => setForm(f => ({ ...f, guest_phone: e.target.value }))} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Room</Label>
                <Select value={form.room_id} onValueChange={(v) => setForm(f => ({ ...f, room_id: v }))}>
                  <SelectTrigger><SelectValue placeholder="Select room" /></SelectTrigger>
                  <SelectContent>
                    {rooms.map(r => <SelectItem key={r.id} value={r.id}>{r.name} — {formatCurrency(r.base_price)}/night</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Check-in</Label>
                  <Input type="date" value={form.check_in} onChange={(e) => setForm(f => ({ ...f, check_in: e.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label>Check-out</Label>
                  <Input type="date" value={form.check_out} onChange={(e) => setForm(f => ({ ...f, check_out: e.target.value }))} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Guests</Label>
                  <Input type="number" value={form.guests} onChange={(e) => setForm(f => ({ ...f, guests: parseInt(e.target.value) || 1 }))} />
                </div>
                <div className="space-y-2">
                  <Label>Total (₹)</Label>
                  <Input type="number" value={form.total_amount} onChange={(e) => setForm(f => ({ ...f, total_amount: parseFloat(e.target.value) || 0 }))} />
                </div>
              </div>
              <Button onClick={handleCreate} className="w-full">Create Booking</Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>

        {/* Bulk booking dialog */}
        <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
          <DialogContent className="max-w-5xl">
            <DialogHeader>
              <DialogTitle>Bulk Booking — multi-row form</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Each row is one booking. Different guests, rooms, and dates allowed. All-or-nothing: if any row fails validation, none are created.
              </p>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-44">Guest name</TableHead>
                      <TableHead className="w-40">Email</TableHead>
                      <TableHead className="w-32">Phone</TableHead>
                      <TableHead className="w-44">Room</TableHead>
                      <TableHead className="w-36">Check-in</TableHead>
                      <TableHead className="w-36">Check-out</TableHead>
                      <TableHead className="w-16">Guests</TableHead>
                      <TableHead className="w-28">Total</TableHead>
                      <TableHead className="w-8" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {bulkRows.map((r, i) => (
                      <TableRow key={i}>
                        <TableCell><Input value={r.guest_name} onChange={e => updateBulkRow(i, { guest_name: e.target.value })} className="h-8" /></TableCell>
                        <TableCell><Input value={r.guest_email} onChange={e => updateBulkRow(i, { guest_email: e.target.value })} className="h-8" /></TableCell>
                        <TableCell><Input value={r.guest_phone} onChange={e => updateBulkRow(i, { guest_phone: e.target.value })} className="h-8" /></TableCell>
                        <TableCell>
                          <Select value={r.room_id} onValueChange={v => updateBulkRow(i, { room_id: v })}>
                            <SelectTrigger className="h-8"><SelectValue placeholder="Room" /></SelectTrigger>
                            <SelectContent>{rooms.map(rm => <SelectItem key={rm.id} value={rm.id}>{rm.name}</SelectItem>)}</SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell><Input type="date" value={r.check_in} onChange={e => updateBulkRow(i, { check_in: e.target.value })} className="h-8" /></TableCell>
                        <TableCell><Input type="date" value={r.check_out} onChange={e => updateBulkRow(i, { check_out: e.target.value })} className="h-8" /></TableCell>
                        <TableCell><Input type="number" min={1} value={r.guests} onChange={e => updateBulkRow(i, { guests: parseInt(e.target.value) || 1 })} className="h-8" /></TableCell>
                        <TableCell><Input type="number" value={r.total_amount} onChange={e => updateBulkRow(i, { total_amount: parseFloat(e.target.value) || 0 })} className="h-8" /></TableCell>
                        <TableCell>
                          {bulkRows.length > 1 && (
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setBulkRows(prev => prev.filter((_, j) => j !== i))}>
                              <X className="w-3 h-3" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="flex items-center justify-between">
                <Button variant="outline" size="sm" onClick={() => setBulkRows(prev => [...prev, blankBulkRow()])}>
                  <Plus className="w-4 h-4 mr-1" />Add row
                </Button>
                <Button onClick={handleBulkCreate} disabled={bulkSubmitting}>
                  {bulkSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Create {bulkRows.filter(r => r.guest_name && r.room_id && r.check_in && r.check_out).length} bookings
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Transfer room dialog */}
        <Dialog open={transferOpen} onOpenChange={setTransferOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Transfer Room</DialogTitle>
            </DialogHeader>
            {transferBooking && (
              <div className="space-y-4">
                <div className="text-sm space-y-1 p-3 rounded-lg bg-muted/50">
                  <p><span className="text-muted-foreground">Guest:</span> {transferBooking.guest_name}</p>
                  <p><span className="text-muted-foreground">Current room:</span> {(transferBooking as any).rooms?.name || "—"}</p>
                  <p><span className="text-muted-foreground">Stay:</span> {formatDate(transferBooking.check_in)} → {formatDate(transferBooking.check_out)}</p>
                </div>
                <div className="space-y-2">
                  <Label>New Room</Label>
                  <Select value={transferRoomId} onValueChange={setTransferRoomId}>
                    <SelectTrigger><SelectValue placeholder="Pick an available room" /></SelectTrigger>
                    <SelectContent>
                      {rooms.filter(r => r.id !== transferBooking.room_id).map(r => (
                        <SelectItem key={r.id} value={r.id}>{r.name} — {formatCurrency(r.base_price)}/night</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    The system checks the new room is available for these dates before transferring.
                  </p>
                </div>
                <Button onClick={handleTransfer} disabled={!transferRoomId || transferSubmitting} className="w-full">
                  {transferSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Transfer to selected room
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <Card className="animate-pulse"><CardContent className="p-6"><div className="h-48 bg-muted rounded" /></CardContent></Card>
      ) : bookings.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <CalendarDays className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No bookings yet</h3>
            <p className="text-muted-foreground mt-1">Create your first booking</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Guest</TableHead>
                  <TableHead>Room</TableHead>
                  <TableHead>Check-in</TableHead>
                  <TableHead>Check-out</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Payment</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bookings.map((b) => (
                  <TableRow key={b.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{b.guest_name}</p>
                        {b.guest_email && <p className="text-xs text-muted-foreground">{b.guest_email}</p>}
                      </div>
                    </TableCell>
                    <TableCell>{(b as any).rooms?.name || "—"}</TableCell>
                    <TableCell>{formatDate(b.check_in)}</TableCell>
                    <TableCell>{formatDate(b.check_out)}</TableCell>
                    <TableCell className="font-medium">{formatCurrency(b.total_amount)}</TableCell>
                    <TableCell>
                      <Select value={b.status} onValueChange={(v) => handleStatusUpdate(b.id, v)}>
                        <SelectTrigger className="h-7 w-28 text-xs border-0 p-0 shadow-none focus:ring-0">
                          <SelectValue>{statusBadge(b.status)}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="pending">pending</SelectItem>
                          <SelectItem value="confirmed">confirmed</SelectItem>
                          <SelectItem value="completed">completed</SelectItem>
                          <SelectItem value="cancelled">cancelled</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Select value={b.payment_status} onValueChange={(v) => handlePaymentUpdate(b.id, v)}>
                        <SelectTrigger className="h-7 w-24 text-xs border-0 p-0 shadow-none focus:ring-0">
                          <SelectValue>{paymentBadge(b.payment_status)}</SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="unpaid">unpaid</SelectItem>
                          <SelectItem value="partial">partial</SelectItem>
                          <SelectItem value="paid">paid</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell className="text-right">
                      {b.status !== "cancelled" && b.status !== "completed" && (
                        <Button variant="ghost" size="sm" onClick={() => openTransfer(b)} title="Transfer to another room">
                          <ArrowRightLeft className="w-3.5 h-3.5 mr-1" />
                          Transfer
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
};

export default Bookings;
