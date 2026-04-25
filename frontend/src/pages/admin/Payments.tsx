import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { formatCurrency, formatDate } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";
import { Plus, CreditCard, FileText } from "lucide-react";

interface Booking {
  id: string; guest_name: string; guest_email: string;
  check_in: string; check_out: string; total_amount: number;
  amount_paid: number; payment_status: string; status: string;
  room_name?: string;
}

interface Payment {
  id: string; booking_id: string; amount: number;
  payment_method: string; payment_date: string; notes: string;
}

interface Invoice {
  id: string; booking_id: string; invoice_number: string;
  amount: number; status: string; issued_at: string; due_date: string;
  guest_name: string; guest_email: string;
}

const paymentStatusColor: Record<string, string> = {
  unpaid: "bg-red-100 text-red-700",
  partial: "bg-yellow-100 text-yellow-700",
  paid: "bg-green-100 text-green-700",
};

const Payments = () => {
  const { tenantId } = useAuth();
  const { toast } = useToast();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [payDialog, setPayDialog] = useState<string | null>(null);
  const [invoiceDialog, setInvoiceDialog] = useState<string | null>(null);
  const [bookingPayments, setBookingPayments] = useState<Payment[]>([]);
  const [payForm, setPayForm] = useState({ amount: "", payment_method: "cash", payment_date: new Date().toISOString().slice(0, 10), notes: "" });

  const fetchData = async () => {
    if (!tenantId) return;
    try {
      const [b, inv] = await Promise.all([
        api.get<any[]>("/api/bookings"),
        api.get<any[]>("/api/invoices"),
      ]);
      setBookings((b || []).map((x: any) => ({ ...x, room_name: x.room_name || "—" })));
      setInvoices(inv || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [tenantId]);

  const openPayDialog = async (bookingId: string) => {
    setPayDialog(bookingId);
    try {
      const payments = await api.get<Payment[]>(`/api/bookings/${bookingId}/payments`);
      setBookingPayments(payments || []);
    } catch { setBookingPayments([]); }
  };

  const handleRecordPayment = async () => {
    if (!payDialog) return;
    const amount = parseFloat(payForm.amount);
    if (!amount || amount <= 0) { toast({ title: "Enter a valid amount", variant: "destructive" }); return; }
    try {
      await api.post(`/api/bookings/${payDialog}/payments`, {
        amount, payment_method: payForm.payment_method,
        payment_date: payForm.payment_date, notes: payForm.notes,
      });
      toast({ title: "Payment recorded" });
      setPayDialog(null);
      setPayForm({ amount: "", payment_method: "cash", payment_date: new Date().toISOString().slice(0, 10), notes: "" });
      fetchData();
    } catch (err: any) { toast({ title: "Error", description: err.message, variant: "destructive" }); }
  };

  const handleCreateInvoice = async (bookingId: string) => {
    try {
      await api.post("/api/invoices", { booking_id: bookingId });
      toast({ title: "Invoice created" });
      fetchData();
    } catch (err: any) { toast({ title: "Error", description: err.message, variant: "destructive" }); }
  };

  const unpaidBookings = bookings.filter(b => b.payment_status !== "paid" && b.status !== "cancelled");
  const outstanding = unpaidBookings.reduce((s, b) => s + Math.max(0, b.total_amount - (b.amount_paid || 0)), 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Payments & Invoices</h1>
        <p className="text-muted-foreground mt-1">Track payments and generate invoices</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card><CardContent className="p-4">
          <p className="text-sm text-muted-foreground">Outstanding</p>
          <p className="text-2xl font-bold text-red-600">{formatCurrency(outstanding)}</p>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <p className="text-sm text-muted-foreground">Unpaid Bookings</p>
          <p className="text-2xl font-bold">{unpaidBookings.length}</p>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <p className="text-sm text-muted-foreground">Invoices</p>
          <p className="text-2xl font-bold">{invoices.length}</p>
        </CardContent></Card>
      </div>

      <Tabs defaultValue="payments">
        <TabsList>
          <TabsTrigger value="payments"><CreditCard className="w-4 h-4 mr-2" />Payments</TabsTrigger>
          <TabsTrigger value="invoices"><FileText className="w-4 h-4 mr-2" />Invoices</TabsTrigger>
        </TabsList>

        <TabsContent value="payments" className="mt-4">
          <Card>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Guest</TableHead>
                    <TableHead>Dates</TableHead>
                    <TableHead>Total</TableHead>
                    <TableHead>Paid</TableHead>
                    <TableHead>Outstanding</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">Loading...</TableCell></TableRow>
                  ) : bookings.filter(b => b.status !== "cancelled").map(b => (
                    <TableRow key={b.id}>
                      <TableCell>
                        <p className="font-medium">{b.guest_name}</p>
                        <p className="text-xs text-muted-foreground">{b.guest_email}</p>
                      </TableCell>
                      <TableCell className="text-sm">{formatDate(b.check_in)} → {formatDate(b.check_out)}</TableCell>
                      <TableCell>{formatCurrency(b.total_amount)}</TableCell>
                      <TableCell className="text-green-600">{formatCurrency(b.amount_paid || 0)}</TableCell>
                      <TableCell className="text-red-600">{formatCurrency(Math.max(0, b.total_amount - (b.amount_paid || 0)))}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${paymentStatusColor[b.payment_status] || ""}`}>
                          {b.payment_status}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={() => openPayDialog(b.id)}>
                            <Plus className="w-3 h-3 mr-1" />Record
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => handleCreateInvoice(b.id)}>
                            <FileText className="w-3 h-3 mr-1" />Invoice
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="invoices" className="mt-4">
          <Card>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice #</TableHead>
                    <TableHead>Guest</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Issued</TableHead>
                    <TableHead>Due</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoices.length === 0 ? (
                    <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground">No invoices yet — create one from Payments tab</TableCell></TableRow>
                  ) : invoices.map(inv => (
                    <TableRow key={inv.id}>
                      <TableCell className="font-mono font-medium">{inv.invoice_number}</TableCell>
                      <TableCell>
                        <p className="font-medium">{inv.guest_name}</p>
                        <p className="text-xs text-muted-foreground">{inv.guest_email}</p>
                      </TableCell>
                      <TableCell>{formatCurrency(inv.amount)}</TableCell>
                      <TableCell>
                        <Badge variant={inv.status === "paid" ? "default" : "secondary"}>{inv.status}</Badge>
                      </TableCell>
                      <TableCell>{formatDate(inv.issued_at)}</TableCell>
                      <TableCell>{inv.due_date ? formatDate(inv.due_date) : "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Record Payment Dialog */}
      <Dialog open={!!payDialog} onOpenChange={(o) => !o && setPayDialog(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Record Payment</DialogTitle></DialogHeader>
          {bookingPayments.length > 0 && (
            <div className="mb-4">
              <p className="text-sm font-medium mb-2">Previous payments:</p>
              {bookingPayments.map(p => (
                <div key={p.id} className="flex justify-between text-sm py-1 border-b">
                  <span>{formatDate(p.payment_date)} · {p.payment_method}</span>
                  <span className="font-medium text-green-600">{formatCurrency(p.amount)}</span>
                </div>
              ))}
            </div>
          )}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Amount (₹)</Label>
              <Input type="number" value={payForm.amount} onChange={e => setPayForm(f => ({ ...f, amount: e.target.value }))} placeholder="0.00" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Method</Label>
                <Select value={payForm.payment_method} onValueChange={v => setPayForm(f => ({ ...f, payment_method: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {["cash", "card", "bank_transfer", "upi", "cheque", "other"].map(m => (
                      <SelectItem key={m} value={m}>{m}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Date</Label>
                <Input type="date" value={payForm.payment_date} onChange={e => setPayForm(f => ({ ...f, payment_date: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Notes</Label>
              <Input value={payForm.notes} onChange={e => setPayForm(f => ({ ...f, notes: e.target.value }))} placeholder="Optional" />
            </div>
            <Button onClick={handleRecordPayment} className="w-full">Record Payment</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Payments;
