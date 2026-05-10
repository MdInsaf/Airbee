import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { formatCurrency } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";
import { Plus, BedDouble, Users, Pencil, Trash2, DatabaseZap, FolderPlus, Loader2 } from "lucide-react";

interface Room {
  id: string;
  name: string;
  description: string | null;
  max_guests: number;
  base_price: number;
  status: string;
  housekeeping_status: string;
  category_id: string | null;
  amenities: any;
  images: any;
}

interface RoomCategory {
  id: string;
  name: string;
  color: string;
}

const Rooms = () => {
  const { tenantId } = useAuth();
  const { toast } = useToast();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [categories, setCategories] = useState<RoomCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRoom, setEditingRoom] = useState<Room | null>(null);

  const [form, setForm] = useState({
    name: "", description: "", max_guests: 2, base_price: 0,
    status: "available" as string, category_id: "" as string,
    count: 1, start_number: 1, name_prefix: "",
  });

  const [catOpen, setCatOpen] = useState(false);
  const [catSubmitting, setCatSubmitting] = useState(false);
  const [catForm, setCatForm] = useState({
    name: "", color: "#3B82F6", description: "",
    count: 0, start_number: 101, room_name_prefix: "",
    base_price: 0, max_guests: 2,
  });

  const fetchData = async () => {
    if (!tenantId) return;
    try {
      const [rooms, settingsData] = await Promise.all([
        api.get<Room[]>("/api/rooms"),
        api.get<{ room_categories: RoomCategory[] }>("/api/settings"),
      ]);
      setRooms(rooms || []);
      setCategories(settingsData.room_categories || []);
    } catch (err) {
      console.error("Rooms fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [tenantId]);

  const resetForm = () => {
    setForm({ name: "", description: "", max_guests: 2, base_price: 0, status: "available", category_id: "", count: 1, start_number: 1, name_prefix: "" });
    setEditingRoom(null);
  };

  const handleSave = async () => {
    if (!tenantId || !form.name) return;
    const isBulk = !editingRoom && form.count > 1;
    const payload: Record<string, any> = {
      name: form.name,
      description: form.description || null,
      max_guests: form.max_guests,
      base_price: form.base_price,
      status: form.status,
      category_id: form.category_id || null,
    };
    if (isBulk) {
      payload.count = form.count;
      payload.start_number = form.start_number;
      if (form.name_prefix) payload.name_prefix = form.name_prefix;
    }
    try {
      if (editingRoom) {
        await api.put(`/api/rooms/${editingRoom.id}`, payload);
      } else {
        await api.post("/api/rooms", payload);
      }
      toast({
        title: editingRoom ? "Room updated" : isBulk ? `${form.count} rooms created` : "Room created",
      });
      setDialogOpen(false);
      resetForm();
      fetchData();
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  const handleCreateCategory = async () => {
    if (!catForm.name) return;
    setCatSubmitting(true);
    try {
      const res = await api.post<{ id: string; rooms_count: number }>("/api/settings/room-categories", {
        name: catForm.name,
        color: catForm.color,
        description: catForm.description || null,
        count: catForm.count,
        start_number: catForm.start_number,
        room_name_prefix: catForm.room_name_prefix || catForm.name,
        base_price: catForm.base_price,
        max_guests: catForm.max_guests,
      });
      toast({
        title: "Category created",
        description: res.rooms_count > 0 ? `Provisioned ${res.rooms_count} rooms` : undefined,
      });
      setCatOpen(false);
      setCatForm({ name: "", color: "#3B82F6", description: "", count: 0, start_number: 101, room_name_prefix: "", base_price: 0, max_guests: 2 });
      fetchData();
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setCatSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/rooms/${id}`);
      toast({ title: "Room deleted" });
      fetchData();
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  const handleSeedDemo = async () => {
    if (!tenantId) return;
    setSeeding(true);
    try {
      const result = await api.post<{
        success: boolean;
        summary: { rooms: number; guests: number; bookings: number };
      }>("/api/demo/seed", {});
      toast({
        title: "Demo data loaded",
        description: `Added ${result.summary.rooms} rooms, ${result.summary.guests} guests, and ${result.summary.bookings} bookings.`,
      });
      await fetchData();
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setSeeding(false);
    }
  };

  const openEdit = (room: Room) => {
    setEditingRoom(room);
    setForm({
      name: room.name,
      description: room.description || "",
      max_guests: room.max_guests,
      base_price: Number(room.base_price),
      status: room.status,
      category_id: room.category_id || "",
    });
    setDialogOpen(true);
  };

  const statusColor = (s: string) => {
    switch (s) {
      case "available": return "bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]";
      case "maintenance": return "bg-[hsl(var(--warning))]/10 text-[hsl(var(--warning))]";
      default: return "bg-destructive/10 text-destructive";
    }
  };

  const hkColor = (s: string) => {
    switch (s) {
      case "clean": return "bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]";
      case "dirty": return "bg-destructive/10 text-destructive";
      default: return "bg-[hsl(var(--warning))]/10 text-[hsl(var(--warning))]";
    }
  };

  const getCategoryName = (id: string | null) => categories.find(c => c.id === id)?.name || "Uncategorized";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Rooms</h1>
          <p className="text-muted-foreground mt-1">Manage your property rooms</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleSeedDemo} disabled={seeding}>
            <DatabaseZap className="w-4 h-4 mr-2" />
            {seeding ? "Loading Demo..." : "Load Demo Data"}
          </Button>
          <Button variant="outline" onClick={() => setCatOpen(true)}>
            <FolderPlus className="w-4 h-4 mr-2" />
            New Category
          </Button>
        <Dialog open={dialogOpen} onOpenChange={(o) => { setDialogOpen(o); if (!o) resetForm(); }}>
          <DialogTrigger asChild>
            <Button><Plus className="w-4 h-4 mr-2" />Add Room</Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{editingRoom ? "Edit Room" : "Add New Room"}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Room Name</Label>
                <Input value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Room 101" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Max Guests</Label>
                  <Input type="number" value={form.max_guests} onChange={(e) => setForm(f => ({ ...f, max_guests: parseInt(e.target.value) || 2 }))} />
                </div>
                <div className="space-y-2">
                  <Label>Base Price (₹)</Label>
                  <Input type="number" value={form.base_price} onChange={(e) => setForm(f => ({ ...f, base_price: parseFloat(e.target.value) || 0 }))} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Status</Label>
                  <Select value={form.status} onValueChange={(v) => setForm(f => ({ ...f, status: v }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="available">Available</SelectItem>
                      <SelectItem value="maintenance">Maintenance</SelectItem>
                      <SelectItem value="unavailable">Unavailable</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Select value={form.category_id} onValueChange={(v) => setForm(f => ({ ...f, category_id: v }))}>
                    <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {categories.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {!editingRoom && (
                <div className="space-y-3 rounded-lg border p-3 bg-muted/30">
                  <div className="flex items-center justify-between">
                    <Label className="font-semibold">Bulk add</Label>
                    <span className="text-xs text-muted-foreground">Set Count &gt; 1 to provision multiple rooms with unique numbers</span>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="space-y-1">
                      <Label className="text-xs">Count</Label>
                      <Input type="number" min={1} max={500} value={form.count} onChange={e => setForm(f => ({ ...f, count: Math.max(1, parseInt(e.target.value) || 1) }))} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Starting #</Label>
                      <Input type="number" value={form.start_number} onChange={e => setForm(f => ({ ...f, start_number: parseInt(e.target.value) || 1 }))} disabled={form.count <= 1} />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Name prefix</Label>
                      <Input placeholder={form.name || "(uses Room Name)"} value={form.name_prefix} onChange={e => setForm(f => ({ ...f, name_prefix: e.target.value }))} disabled={form.count <= 1} />
                    </div>
                  </div>
                  {form.count > 1 && (
                    <p className="text-xs text-muted-foreground">
                      Will create rooms named <span className="font-mono">{(form.name_prefix || form.name || "Room")} {form.start_number}</span>
                      {" … "}
                      <span className="font-mono">{(form.name_prefix || form.name || "Room")} {form.start_number + form.count - 1}</span>
                    </p>
                  )}
                </div>
              )}
              <Button onClick={handleSave} className="w-full">
                {editingRoom ? "Update Room" : form.count > 1 ? `Create ${form.count} Rooms` : "Create Room"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        </div>
      </div>

      {/* Create Category dialog (with optional bulk room provisioning) */}
      <Dialog open={catOpen} onOpenChange={setCatOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>New Room Category</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Category Name</Label>
              <Input value={catForm.name} onChange={e => setCatForm(f => ({ ...f, name: e.target.value }))} placeholder="e.g. Deluxe" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Color</Label>
                <Input type="color" value={catForm.color} onChange={e => setCatForm(f => ({ ...f, color: e.target.value }))} className="h-9 p-1" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Input value={catForm.description} onChange={e => setCatForm(f => ({ ...f, description: e.target.value }))} />
              </div>
            </div>
            <div className="space-y-3 rounded-lg border p-3 bg-muted/30">
              <Label className="font-semibold">Provision rooms in this category</Label>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Count</Label>
                  <Input type="number" min={0} max={500} value={catForm.count} onChange={e => setCatForm(f => ({ ...f, count: Math.max(0, parseInt(e.target.value) || 0) }))} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Starting #</Label>
                  <Input type="number" value={catForm.start_number} onChange={e => setCatForm(f => ({ ...f, start_number: parseInt(e.target.value) || 1 }))} disabled={catForm.count === 0} />
                </div>
                <div className="space-y-1 col-span-2">
                  <Label className="text-xs">Room name prefix</Label>
                  <Input placeholder={catForm.name || "(uses category name)"} value={catForm.room_name_prefix} onChange={e => setCatForm(f => ({ ...f, room_name_prefix: e.target.value }))} disabled={catForm.count === 0} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Base price (₹)</Label>
                  <Input type="number" value={catForm.base_price} onChange={e => setCatForm(f => ({ ...f, base_price: parseFloat(e.target.value) || 0 }))} disabled={catForm.count === 0} />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Max guests</Label>
                  <Input type="number" min={1} value={catForm.max_guests} onChange={e => setCatForm(f => ({ ...f, max_guests: parseInt(e.target.value) || 2 }))} disabled={catForm.count === 0} />
                </div>
              </div>
              {catForm.count > 0 && (
                <p className="text-xs text-muted-foreground">
                  Will provision {catForm.count} room{catForm.count > 1 ? "s" : ""}: <span className="font-mono">
                    {(catForm.room_name_prefix || catForm.name || "Room")} {catForm.start_number}
                    {catForm.count > 1 && ` … ${(catForm.room_name_prefix || catForm.name || "Room")} ${catForm.start_number + catForm.count - 1}`}
                  </span>
                </p>
              )}
            </div>
            <Button onClick={handleCreateCategory} disabled={!catForm.name || catSubmitting} className="w-full">
              {catSubmitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {catForm.count > 0 ? `Create category + ${catForm.count} rooms` : "Create category"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3].map(i => <Card key={i} className="animate-pulse"><CardContent className="p-6"><div className="h-32 bg-muted rounded" /></CardContent></Card>)}
        </div>
      ) : rooms.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <BedDouble className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No rooms yet</h3>
            <p className="text-muted-foreground mt-1">Add your first room or load demo inventory to populate the dashboard and booking flow.</p>
            <div className="mt-6 flex justify-center">
              <Button variant="outline" onClick={handleSeedDemo} disabled={seeding}>
                <DatabaseZap className="w-4 h-4 mr-2" />
                {seeding ? "Loading Demo..." : "Load Demo Data"}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rooms.map((room) => (
            <Card key={room.id} className="group hover:shadow-md transition-shadow">
              <CardContent className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-lg">{room.name}</h3>
                    <p className="text-sm text-muted-foreground">{getCategoryName(room.category_id)}</p>
                  </div>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(room)}><Pencil className="w-3.5 h-3.5" /></Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => handleDelete(room.id)}><Trash2 className="w-3.5 h-3.5" /></Button>
                  </div>
                </div>
                <div className="flex items-center gap-2 mb-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(room.status)}`}>
                    {room.status}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${hkColor(room.housekeeping_status)}`}>
                    {room.housekeeping_status}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Users className="w-3.5 h-3.5" />
                    <span>{room.max_guests} guests</span>
                  </div>
                  <span className="font-bold text-lg">{formatCurrency(room.base_price)}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default Rooms;
