import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { Plus, RefreshCw, Trash2, Link, CheckCircle, XCircle, Clock } from "lucide-react";

interface Channel {
  id: string;
  name: string;
  platform: string;
  room_id: string | null;
  room_name: string | null;
  ical_url: string | null;
  last_synced_at: string | null;
  sync_status: string;
  sync_error: string | null;
  created_at: string;
}

interface Room {
  id: string;
  name: string;
}

const PLATFORM_LABELS: Record<string, string> = {
  airbnb: "Airbnb",
  bookingcom: "Booking.com",
  expedia: "Expedia",
  makemytrip: "MakeMyTrip",
  other: "Other",
};

const PLATFORM_COLORS: Record<string, string> = {
  airbnb: "bg-rose-100 text-rose-700",
  bookingcom: "bg-blue-100 text-blue-700",
  expedia: "bg-yellow-100 text-yellow-700",
  makemytrip: "bg-red-100 text-red-700",
  other: "bg-gray-100 text-gray-700",
};

function SyncStatusBadge({ status, error }: { status: string; error: string | null }) {
  if (status === "success") return (
    <span className="flex items-center gap-1 text-green-600 text-sm">
      <CheckCircle className="h-4 w-4" /> Synced
    </span>
  );
  if (status === "error") return (
    <span className="flex items-center gap-1 text-red-600 text-sm" title={error ?? ""}>
      <XCircle className="h-4 w-4" /> Error
    </span>
  );
  return (
    <span className="flex items-center gap-1 text-gray-400 text-sm">
      <Clock className="h-4 w-4" /> Never synced
    </span>
  );
}

export default function Channels() {
  const { toast } = useToast();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", platform: "other", room_id: "", ical_url: "" });

  const load = async () => {
    try {
      const [chRes, rmRes] = await Promise.all([
        api.get<{ channels: Channel[] }>("/api/channels"),
        api.get<{ rooms: Room[] }>("/api/rooms"),
      ]);
      setChannels(chRes.channels);
      setRooms(rmRes.rooms);
    } catch {
      toast({ title: "Failed to load channels", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    if (!form.name.trim()) {
      toast({ title: "Channel name is required", variant: "destructive" });
      return;
    }
    try {
      await api.post("/api/channels", {
        name: form.name.trim(),
        platform: form.platform,
        room_id: form.room_id || null,
        ical_url: form.ical_url.trim() || null,
      });
      toast({ title: "Channel added" });
      setOpen(false);
      setForm({ name: "", platform: "other", room_id: "", ical_url: "" });
      load();
    } catch {
      toast({ title: "Failed to add channel", variant: "destructive" });
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/channels/${id}`);
      setChannels(prev => prev.filter(c => c.id !== id));
      toast({ title: "Channel removed" });
    } catch {
      toast({ title: "Failed to remove channel", variant: "destructive" });
    }
  };

  const handleSync = async (id: string) => {
    setSyncing(id);
    try {
      const res = await api.post<{ synced: number; skipped: number }>(`/api/channels/${id}/sync`, {});
      toast({ title: `Sync complete — ${res.synced} new bookings imported, ${res.skipped} skipped` });
      load();
    } catch (e: any) {
      toast({ title: "Sync failed", description: e.message, variant: "destructive" });
      load();
    } finally {
      setSyncing(null);
    }
  };

  const getICalExportUrl = (roomId: string) => {
    const apiBase = import.meta.env.VITE_API_URL || "";
    const tenantSlug = "grand-airbee"; // TODO: get from settings context
    return `${apiBase}/public/ical/${tenantSlug}/${roomId}.ics`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Channel Manager</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Sync bookings with OTAs via iCal feeds
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button><Plus className="h-4 w-4 mr-2" />Add Channel</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add OTA Channel</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-2">
              <div className="space-y-1">
                <Label>Channel Name</Label>
                <Input
                  placeholder="e.g. Airbnb - Room 101"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                />
              </div>
              <div className="space-y-1">
                <Label>Platform</Label>
                <Select value={form.platform} onValueChange={v => setForm(f => ({ ...f, platform: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(PLATFORM_LABELS).map(([val, label]) => (
                      <SelectItem key={val} value={val}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>Room</Label>
                <Select value={form.room_id} onValueChange={v => setForm(f => ({ ...f, room_id: v }))}>
                  <SelectTrigger><SelectValue placeholder="Select room" /></SelectTrigger>
                  <SelectContent>
                    {rooms.map(r => (
                      <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>iCal URL (from OTA extranet)</Label>
                <Input
                  placeholder="https://www.airbnb.com/calendar/ical/..."
                  value={form.ical_url}
                  onChange={e => setForm(f => ({ ...f, ical_url: e.target.value }))}
                />
                <p className="text-xs text-muted-foreground">
                  Paste the iCal/ICS export URL from the OTA's calendar settings
                </p>
              </div>
              <Button className="w-full" onClick={handleAdd}>Add Channel</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* iCal Export Section */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Link className="h-4 w-4" /> Your iCal Export URLs
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-3">
            Share these URLs with OTAs so they can subscribe to your room availability.
          </p>
          <div className="space-y-2">
            {rooms.map(room => (
              <div key={room.id} className="flex items-center gap-3 p-2 bg-muted rounded-md">
                <span className="text-sm font-medium w-32 shrink-0">{room.name}</span>
                <code className="text-xs flex-1 truncate text-muted-foreground">
                  {getICalExportUrl(room.id)}
                </code>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    navigator.clipboard.writeText(getICalExportUrl(room.id));
                    toast({ title: "Copied to clipboard" });
                  }}
                >
                  Copy
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Channel List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Connected Channels</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : channels.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No channels connected yet. Add an OTA channel above to start syncing.
            </p>
          ) : (
            <div className="space-y-3">
              {channels.map(ch => (
                <div key={ch.id} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{ch.name}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PLATFORM_COLORS[ch.platform] ?? PLATFORM_COLORS.other}`}>
                        {PLATFORM_LABELS[ch.platform] ?? ch.platform}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      {ch.room_name && <span>Room: {ch.room_name}</span>}
                      {ch.last_synced_at && (
                        <span>Last sync: {new Date(ch.last_synced_at).toLocaleString()}</span>
                      )}
                    </div>
                    <SyncStatusBadge status={ch.sync_status} error={ch.sync_error} />
                    {ch.sync_error && (
                      <p className="text-xs text-red-500">{ch.sync_error}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={syncing === ch.id || !ch.ical_url}
                      onClick={() => handleSync(ch.id)}
                    >
                      <RefreshCw className={`h-4 w-4 mr-1 ${syncing === ch.id ? "animate-spin" : ""}`} />
                      Sync
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      onClick={() => handleDelete(ch.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
