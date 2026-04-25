import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { Plus, Pencil, Trash2, Tag } from "lucide-react";

interface Rule {
  id: string; name: string; rule_type: string; adjustment_type: string;
  adjustment_value: number; start_date: string; end_date: string;
  min_nights: number; priority: number; is_active: boolean; room_name?: string;
}
interface Room { id: string; name: string; }

const RULE_TYPES = ["seasonal", "weekend", "holiday", "last_minute", "early_bird", "minimum_stay"];
const ADJ_TYPES = ["percentage", "fixed"];

const emptyForm = { name: "", rule_type: "seasonal", adjustment_type: "percentage", adjustment_value: 0, start_date: "", end_date: "", min_nights: 1, priority: 1, is_active: true, room_id: "" };

const PricingRules = () => {
  const { tenantId } = useAuth();
  const { toast } = useToast();
  const [rules, setRules] = useState<Rule[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);

  const fetchData = async () => {
    if (!tenantId) return;
    try {
      const [r, rooms_] = await Promise.all([api.get<Rule[]>("/api/pricing-rules"), api.get<Room[]>("/api/rooms")]);
      setRules(r || []);
      setRooms(rooms_ || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [tenantId]);

  const openCreate = () => { setEditId(null); setForm(emptyForm); setDialog(true); };
  const openEdit = (r: Rule) => {
    setEditId(r.id);
    setForm({ name: r.name, rule_type: r.rule_type, adjustment_type: r.adjustment_type, adjustment_value: r.adjustment_value, start_date: r.start_date || "", end_date: r.end_date || "", min_nights: r.min_nights || 1, priority: r.priority || 1, is_active: r.is_active, room_id: "" });
    setDialog(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast({ title: "Name is required", variant: "destructive" }); return; }
    try {
      if (editId) {
        await api.put(`/api/pricing-rules/${editId}`, form);
      } else {
        await api.post("/api/pricing-rules", form);
      }
      toast({ title: editId ? "Rule updated" : "Rule created" });
      setDialog(false);
      fetchData();
    } catch (err: any) { toast({ title: "Error", description: err.message, variant: "destructive" }); }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/pricing-rules/${id}`);
      toast({ title: "Rule deleted" });
      fetchData();
    } catch (err: any) { toast({ title: "Error", description: err.message, variant: "destructive" }); }
  };

  const toggleActive = async (rule: Rule) => {
    try {
      await api.put(`/api/pricing-rules/${rule.id}`, { is_active: !rule.is_active });
      setRules(prev => prev.map(r => r.id === rule.id ? { ...r, is_active: !r.is_active } : r));
    } catch { toast({ title: "Error toggling rule", variant: "destructive" }); }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Pricing Rules</h1>
          <p className="text-muted-foreground mt-1">Seasonal rates, weekend surcharges, and more</p>
        </div>
        <Button onClick={openCreate}><Plus className="w-4 h-4 mr-2" />New Rule</Button>
      </div>

      {loading ? (
        <Card><CardContent className="p-6"><div className="h-48 bg-muted rounded animate-pulse" /></CardContent></Card>
      ) : rules.length === 0 ? (
        <Card><CardContent className="p-12 text-center">
          <Tag className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">No pricing rules</h3>
          <p className="text-muted-foreground mt-1">Add seasonal or weekend pricing adjustments</p>
        </CardContent></Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Adjustment</TableHead>
                  <TableHead>Period</TableHead>
                  <TableHead>Room</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map(rule => (
                  <TableRow key={rule.id}>
                    <TableCell className="font-medium">{rule.name}</TableCell>
                    <TableCell><span className="px-2 py-0.5 rounded bg-muted text-xs">{rule.rule_type}</span></TableCell>
                    <TableCell>
                      <span className={rule.adjustment_value >= 0 ? "text-green-600" : "text-red-600"}>
                        {rule.adjustment_value >= 0 ? "+" : ""}{rule.adjustment_value}{rule.adjustment_type === "percentage" ? "%" : " ₹"}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {rule.start_date ? `${rule.start_date} → ${rule.end_date || "..."}` : "Always"}
                    </TableCell>
                    <TableCell className="text-sm">{rule.room_name || "All rooms"}</TableCell>
                    <TableCell>{rule.priority}</TableCell>
                    <TableCell>
                      <Switch checked={rule.is_active} onCheckedChange={() => toggleActive(rule)} />
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(rule)}><Pencil className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => handleDelete(rule.id)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}

      <Dialog open={dialog} onOpenChange={setDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>{editId ? "Edit Rule" : "New Pricing Rule"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Rule Name</Label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Weekend Surcharge" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Rule Type</Label>
                <Select value={form.rule_type} onValueChange={v => setForm(f => ({ ...f, rule_type: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{RULE_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Room (optional)</Label>
                <Select value={form.room_id} onValueChange={v => setForm(f => ({ ...f, room_id: v }))}>
                  <SelectTrigger><SelectValue placeholder="All rooms" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All rooms</SelectItem>
                    {rooms.map(r => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Adjustment Type</Label>
                <Select value={form.adjustment_type} onValueChange={v => setForm(f => ({ ...f, adjustment_type: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{ADJ_TYPES.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Value (use negative for discount)</Label>
                <Input type="number" value={form.adjustment_value} onChange={e => setForm(f => ({ ...f, adjustment_value: parseFloat(e.target.value) || 0 }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Start Date</Label>
                <Input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>End Date</Label>
                <Input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Min Nights</Label>
                <Input type="number" min={1} value={form.min_nights} onChange={e => setForm(f => ({ ...f, min_nights: parseInt(e.target.value) || 1 }))} />
              </div>
              <div className="space-y-2">
                <Label>Priority (lower = higher priority)</Label>
                <Input type="number" min={1} value={form.priority} onChange={e => setForm(f => ({ ...f, priority: parseInt(e.target.value) || 1 }))} />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={form.is_active} onCheckedChange={v => setForm(f => ({ ...f, is_active: v }))} />
              <Label>Active</Label>
            </div>
            <Button onClick={handleSave} className="w-full">{editId ? "Update Rule" : "Create Rule"}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PricingRules;
