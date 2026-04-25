import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { Plus, Pencil, Trash2, Users } from "lucide-react";

interface Staff {
  id: string; name: string; email: string; phone: string;
  role: string; department: string; is_active: boolean; notes: string;
}

const ROLES = ["manager", "front_desk", "housekeeping", "maintenance", "staff"];
const ROLE_COLORS: Record<string, string> = {
  manager: "bg-purple-100 text-purple-700",
  front_desk: "bg-blue-100 text-blue-700",
  housekeeping: "bg-green-100 text-green-700",
  maintenance: "bg-orange-100 text-orange-700",
  staff: "bg-gray-100 text-gray-700",
};

const emptyForm = { name: "", email: "", phone: "", role: "staff", department: "", is_active: true, notes: "" };

const StaffManagement = () => {
  const { tenantId } = useAuth();
  const { toast } = useToast();
  const [staff, setStaff] = useState<Staff[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);

  const fetchData = async () => {
    if (!tenantId) return;
    try {
      const data = await api.get<Staff[]>("/api/staff");
      setStaff(data || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [tenantId]);

  const openCreate = () => { setEditId(null); setForm(emptyForm); setDialog(true); };
  const openEdit = (s: Staff) => {
    setEditId(s.id);
    setForm({ name: s.name, email: s.email || "", phone: s.phone || "", role: s.role, department: s.department || "", is_active: s.is_active, notes: s.notes || "" });
    setDialog(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) { toast({ title: "Name is required", variant: "destructive" }); return; }
    try {
      if (editId) await api.put(`/api/staff/${editId}`, form);
      else await api.post("/api/staff", form);
      toast({ title: editId ? "Staff updated" : "Staff added" });
      setDialog(false);
      fetchData();
    } catch (err: any) { toast({ title: "Error", description: err.message, variant: "destructive" }); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Remove this staff member?")) return;
    try {
      await api.delete(`/api/staff/${id}`);
      toast({ title: "Staff removed" });
      fetchData();
    } catch (err: any) { toast({ title: "Error", description: err.message, variant: "destructive" }); }
  };

  const toggleActive = async (s: Staff) => {
    try {
      await api.put(`/api/staff/${s.id}`, { is_active: !s.is_active });
      setStaff(prev => prev.map(m => m.id === s.id ? { ...m, is_active: !m.is_active } : m));
    } catch { toast({ title: "Error", variant: "destructive" }); }
  };

  const activeCount = staff.filter(s => s.is_active).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Staff Management</h1>
          <p className="text-muted-foreground mt-1">{activeCount} active staff members</p>
        </div>
        <Button onClick={openCreate}><Plus className="w-4 h-4 mr-2" />Add Staff</Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {ROLES.map(role => {
          const count = staff.filter(s => s.role === role && s.is_active).length;
          return (
            <Card key={role}><CardContent className="p-4">
              <p className="text-xs text-muted-foreground capitalize">{role.replace("_", " ")}</p>
              <p className="text-xl font-bold">{count}</p>
            </CardContent></Card>
          );
        })}
      </div>

      {loading ? (
        <Card><CardContent className="p-6"><div className="h-48 bg-muted rounded animate-pulse" /></CardContent></Card>
      ) : staff.length === 0 ? (
        <Card><CardContent className="p-12 text-center">
          <Users className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">No staff members</h3>
          <p className="text-muted-foreground mt-1">Add your team members</p>
        </CardContent></Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {staff.map(s => (
                  <TableRow key={s.id} className={!s.is_active ? "opacity-50" : ""}>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[s.role] || "bg-gray-100"}`}>
                        {s.role.replace("_", " ")}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{s.department || "—"}</TableCell>
                    <TableCell className="text-sm">
                      {s.email && <p>{s.email}</p>}
                      {s.phone && <p className="text-muted-foreground">{s.phone}</p>}
                    </TableCell>
                    <TableCell><Switch checked={s.is_active} onCheckedChange={() => toggleActive(s)} /></TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="icon" onClick={() => openEdit(s)}><Pencil className="w-4 h-4" /></Button>
                        <Button variant="ghost" size="icon" onClick={() => handleDelete(s.id)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
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
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>{editId ? "Edit Staff" : "Add Staff Member"}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2"><Label>Full Name</Label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2"><Label>Role</Label>
                <Select value={form.role} onValueChange={v => setForm(f => ({ ...f, role: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{ROLES.map(r => <SelectItem key={r} value={r}>{r.replace("_", " ")}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-2"><Label>Department</Label>
                <Input value={form.department} onChange={e => setForm(f => ({ ...f, department: e.target.value }))} placeholder="e.g. Operations" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2"><Label>Email</Label>
                <Input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
              </div>
              <div className="space-y-2"><Label>Phone</Label>
                <Input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-2"><Label>Notes</Label>
              <Input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Optional" />
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={form.is_active} onCheckedChange={v => setForm(f => ({ ...f, is_active: v }))} />
              <Label>Active</Label>
            </div>
            <Button onClick={handleSave} className="w-full">{editId ? "Update" : "Add Staff"}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default StaffManagement;
