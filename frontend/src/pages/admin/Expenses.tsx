import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { formatCurrency, formatDate } from "@/lib/format";
import { Plus, Receipt, Trash2 } from "lucide-react";

interface Expense { id: string; category: string; description: string; amount: number; expense_date: string; payment_method: string; notes: string; }

const CATEGORIES = ["utilities", "salaries", "maintenance", "supplies", "food_beverage", "marketing", "laundry", "repairs", "insurance", "taxes", "rent", "other"];
const CATEGORY_COLORS: Record<string, string> = {
  salaries: "bg-purple-100 text-purple-700", utilities: "bg-blue-100 text-blue-700",
  maintenance: "bg-orange-100 text-orange-700", supplies: "bg-green-100 text-green-700",
  food_beverage: "bg-yellow-100 text-yellow-700", marketing: "bg-pink-100 text-pink-700",
  other: "bg-gray-100 text-gray-600",
};

const emptyForm = { category: "other", description: "", amount: "", expense_date: new Date().toISOString().slice(0, 10), payment_method: "cash", notes: "" };

const Expenses = () => {
  const { tenantId } = useAuth();
  const { toast } = useToast();
  const [data, setData] = useState<{ expenses: Expense[]; summary: Record<string, number>; total: number }>({ expenses: [], summary: {}, total: 0 });
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const today = new Date();
  const [fromDate, setFromDate] = useState(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-01`);
  const [toDate, setToDate] = useState(today.toISOString().slice(0, 10));

  const fetchData = async () => {
    if (!tenantId) return;
    try {
      const result = await api.get<any>(`/api/expenses?from=${fromDate}&to=${toDate}`);
      setData(result || { expenses: [], summary: {}, total: 0 });
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [tenantId, fromDate, toDate]);

  const handleCreate = async () => {
    if (!form.description.trim() || !form.amount) { toast({ title: "Description and amount required", variant: "destructive" }); return; }
    try {
      await api.post("/api/expenses", { ...form, amount: parseFloat(form.amount) });
      toast({ title: "Expense recorded" });
      setDialog(false);
      setForm(emptyForm);
      fetchData();
    } catch (err: any) { toast({ title: "Error", description: err.message, variant: "destructive" }); }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/expenses/${id}`);
      toast({ title: "Expense deleted" });
      fetchData();
    } catch { toast({ title: "Error", variant: "destructive" }); }
  };

  const topCategories = Object.entries(data.summary).sort(([, a], [, b]) => b - a).slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Expense Tracking</h1>
          <p className="text-muted-foreground mt-1">Monitor hotel operating costs</p>
        </div>
        <Button onClick={() => setDialog(true)}><Plus className="w-4 h-4 mr-2" />Add Expense</Button>
      </div>

      <div className="flex gap-4 items-end">
        <div className="space-y-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} className="w-36" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={toDate} onChange={e => setToDate(e.target.value)} className="w-36" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="md:col-span-1">
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Total Expenses</p>
            <p className="text-2xl font-bold text-red-600">{formatCurrency(data.total)}</p>
          </CardContent>
        </Card>
        {topCategories.map(([cat, amt]) => (
          <Card key={cat}>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground capitalize">{cat.replace("_", " ")}</p>
              <p className="text-xl font-bold">{formatCurrency(amt)}</p>
              <p className="text-xs text-muted-foreground">{data.total ? Math.round((amt / data.total) * 100) : 0}% of total</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Method</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground">Loading...</TableCell></TableRow>
              ) : data.expenses.length === 0 ? (
                <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                  <Receipt className="w-8 h-8 mx-auto mb-2" />No expenses in this period
                </TableCell></TableRow>
              ) : data.expenses.map(e => (
                <TableRow key={e.id}>
                  <TableCell className="text-sm">{formatDate(e.expense_date)}</TableCell>
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${CATEGORY_COLORS[e.category] || "bg-gray-100"}`}>
                      {e.category.replace("_", " ")}
                    </span>
                  </TableCell>
                  <TableCell className="font-medium">{e.description}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{e.payment_method}</TableCell>
                  <TableCell className="font-medium text-red-600">{formatCurrency(e.amount)}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" onClick={() => handleDelete(e.id)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>

      <Dialog open={dialog} onOpenChange={setDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Record Expense</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2"><Label>Category</Label>
                <Select value={form.category} onValueChange={v => setForm(f => ({ ...f, category: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{CATEGORIES.map(c => <SelectItem key={c} value={c}>{c.replace("_", " ")}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-2"><Label>Date</Label>
                <Input type="date" value={form.expense_date} onChange={e => setForm(f => ({ ...f, expense_date: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-2"><Label>Description</Label>
              <Input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="e.g. Electricity bill June" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2"><Label>Amount (₹)</Label>
                <Input type="number" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))} placeholder="0.00" />
              </div>
              <div className="space-y-2"><Label>Payment Method</Label>
                <Select value={form.payment_method} onValueChange={v => setForm(f => ({ ...f, payment_method: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{["cash", "card", "bank_transfer", "upi", "cheque"].map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2"><Label>Notes</Label>
              <Input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Optional" />
            </div>
            <Button onClick={handleCreate} className="w-full">Record Expense</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Expenses;
