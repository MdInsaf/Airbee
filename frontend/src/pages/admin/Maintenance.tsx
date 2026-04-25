import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { Plus, Wrench } from "lucide-react";
import { formatDate } from "@/lib/format";

interface Request { id: string; room_id: string; room_name: string; title: string; description: string; priority: string; status: string; reported_by: string; resolved_at: string; created_at: string; }
interface Room { id: string; name: string; }

const PRIORITY_COLORS: Record<string, string> = { urgent: "bg-red-100 text-red-700", high: "bg-orange-100 text-orange-700", normal: "bg-blue-100 text-blue-700", low: "bg-gray-100 text-gray-600" };
const STATUS_COLORS: Record<string, string> = { open: "bg-red-100 text-red-700", in_progress: "bg-yellow-100 text-yellow-700", resolved: "bg-green-100 text-green-700", closed: "bg-gray-100 text-gray-600" };

const emptyForm = { title: "", description: "", priority: "normal", room_id: "", reported_by: "" };

const Maintenance = () => {
  const { tenantId } = useAuth();
  const { toast } = useToast();
  const [requests, setRequests] = useState<Request[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [filter, setFilter] = useState("open");
  const [form, setForm] = useState(emptyForm);

  const fetchData = async () => {
    if (!tenantId) return;
    try {
      const [reqs, r] = await Promise.all([api.get<Request[]>("/api/maintenance"), api.get<Room[]>("/api/rooms")]);
      setRequests(reqs || []);
      setRooms(r || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, [tenantId]);

  const handleCreate = async () => {
    if (!form.title.trim()) { toast({ title: "Title required", variant: "destructive" }); return; }
    try {
      await api.post("/api/maintenance", form);
      toast({ title: "Request submitted" });
      setDialog(false);
      setForm(emptyForm);
      fetchData();
    } catch (err: any) { toast({ title: "Error", description: err.message, variant: "destructive" }); }
  };

  const updateStatus = async (id: string, status: string) => {
    try {
      await api.put(`/api/maintenance/${id}`, { status });
      setRequests(prev => prev.map(r => r.id === id ? { ...r, status } : r));
      toast({ title: "Status updated" });
    } catch { toast({ title: "Error", variant: "destructive" }); }
  };

  const filtered = requests.filter(r => filter === "all" || r.status === filter);
  const openCount = requests.filter(r => r.status === "open").length;
  const urgentCount = requests.filter(r => r.priority === "urgent" && r.status !== "resolved" && r.status !== "closed").length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Maintenance</h1>
          <p className="text-muted-foreground mt-1">{openCount} open · {urgentCount} urgent</p>
        </div>
        <Button onClick={() => setDialog(true)}><Plus className="w-4 h-4 mr-2" />New Request</Button>
      </div>

      <div className="flex gap-2">
        {["open", "in_progress", "resolved", "closed", "all"].map(s => (
          <Button key={s} variant={filter === s ? "default" : "outline"} size="sm" onClick={() => setFilter(s)}>
            {s.replace("_", " ")}
          </Button>
        ))}
      </div>

      {loading ? (
        <Card><CardContent className="p-6"><div className="h-48 bg-muted rounded animate-pulse" /></CardContent></Card>
      ) : filtered.length === 0 ? (
        <Card><CardContent className="p-12 text-center">
          <Wrench className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">No {filter} requests</h3>
        </CardContent></Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Room</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Reported by</TableHead>
                  <TableHead>Reported</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Update</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map(req => (
                  <TableRow key={req.id}>
                    <TableCell>
                      <p className="font-medium">{req.title}</p>
                      {req.description && <p className="text-xs text-muted-foreground">{req.description}</p>}
                    </TableCell>
                    <TableCell className="text-sm">{req.room_name || "General"}</TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${PRIORITY_COLORS[req.priority]}`}>{req.priority}</span>
                    </TableCell>
                    <TableCell className="text-sm">{req.reported_by || "—"}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatDate(req.created_at)}</TableCell>
                    <TableCell>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[req.status]}`}>{req.status.replace("_", " ")}</span>
                    </TableCell>
                    <TableCell>
                      <Select value={req.status} onValueChange={v => updateStatus(req.id, v)}>
                        <SelectTrigger className="h-7 w-28 text-xs"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {["open", "in_progress", "resolved", "closed"].map(s => <SelectItem key={s} value={s}>{s.replace("_", " ")}</SelectItem>)}
                        </SelectContent>
                      </Select>
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
          <DialogHeader><DialogTitle>New Maintenance Request</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2"><Label>Title</Label>
              <Input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="e.g. AC not working" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2"><Label>Room</Label>
                <Select value={form.room_id} onValueChange={v => setForm(f => ({ ...f, room_id: v }))}>
                  <SelectTrigger><SelectValue placeholder="Select room" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">General / Common Area</SelectItem>
                    {rooms.map(r => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2"><Label>Priority</Label>
                <Select value={form.priority} onValueChange={v => setForm(f => ({ ...f, priority: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{["low", "normal", "high", "urgent"].map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2"><Label>Description</Label>
              <Textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={3} placeholder="Describe the issue..." />
            </div>
            <div className="space-y-2"><Label>Reported By</Label>
              <Input value={form.reported_by} onChange={e => setForm(f => ({ ...f, reported_by: e.target.value }))} placeholder="Your name" />
            </div>
            <Button onClick={handleCreate} className="w-full">Submit Request</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Maintenance;
