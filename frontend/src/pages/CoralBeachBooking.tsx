import { useMemo, useState } from "react";
import { ArrowRight, CalendarDays, CheckCircle2, Clock3, Mail, MapPin, Phone, ShieldCheck, Sparkles, Users, Waves } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { coralBeachBookingSite, type CoralBeachRoom } from "@/data/coralBeachBooking";

type CoralBeachSearch = {
  checkIn: string;
  checkOut: string;
  adults: number;
  children: number;
  childAge1: number;
  childAge2: number;
};

function formatIsoDate(date: Date) {
  return date.toISOString().split("T")[0];
}

function buildDefaultSearch(): CoralBeachSearch {
  const today = new Date();
  const checkIn = new Date(today);
  checkIn.setDate(today.getDate() + 1);
  const checkOut = new Date(checkIn);
  checkOut.setDate(checkIn.getDate() + 1);

  return {
    checkIn: formatIsoDate(checkIn),
    checkOut: formatIsoDate(checkOut),
    adults: 2,
    children: 0,
    childAge1: 6,
    childAge2: 9,
  };
}

function formatAxisDate(isoDate: string) {
  const [year, month, day] = isoDate.split("-");
  if (!year || !month || !day) return isoDate;
  return `${day}/${month}/${year}`;
}

function formatCurrency(amount: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatReadableDate(isoDate: string) {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return isoDate;
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function buildPaxInfo(search: CoralBeachSearch) {
  if (search.children <= 0) {
    return `${search.adults}|0||`;
  }

  if (search.children === 1) {
    return `${search.adults}|1|${search.childAge1}||`;
  }

  return `${search.adults}|2|${search.childAge1}|${search.childAge2}|`;
}

function submitAxisRoomsForm(
  search: CoralBeachSearch,
  options?: {
    room?: CoralBeachRoom;
    sendToPaymentPage?: boolean;
  }
) {
  const form = document.createElement("form");
  form.method = "post";
  form.action = `https://app.axisrooms.com/beV2/searchHotel.html?bookingEngineId=${coralBeachBookingSite.axisRooms.bookingEngineId}`;
  form.target = "_self";
  form.style.display = "none";

  const values: Record<string, string> = {
    paxInfo: buildPaxInfo(search),
    allHotels: "true",
    newBe: "true",
    bookingEngineId: coralBeachBookingSite.axisRooms.bookingEngineId,
    productId: coralBeachBookingSite.axisRooms.productId,
    fromdate: formatAxisDate(search.checkIn),
    todate: formatAxisDate(search.checkOut),
    rooms: "1",
    searcherId: coralBeachBookingSite.axisRooms.searcherId,
    searchNumber: coralBeachBookingSite.axisRooms.searchNumber,
    applicableDealId: coralBeachBookingSite.axisRooms.applicableDealId,
    dayUse: "false",
    promoCode: "0",
    googlecpc: "0",
    dorm: "false",
    roomId: options?.room?.roomId || "-1",
    ratePlanId: options?.room?.ratePlanId || "-1",
    sendToPaymentPage: options?.sendToPaymentPage ? "true" : "false",
    upperBirth: "0",
    middleBirth: "0",
    lowerBirth: "0",
  };

  Object.entries(values).forEach(([name, value]) => {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  });

  document.body.appendChild(form);
  form.submit();
  form.remove();
}

function MessageBubble() {
  return (
    <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-[#25D366] text-[10px] font-bold text-white">
      W
    </span>
  );
}

const CoralBeachBooking = () => {
  const [search, setSearch] = useState<CoralBeachSearch>(buildDefaultSearch);

  const occupancyText = useMemo(() => {
    const totalGuests = search.adults + search.children;
    return `${totalGuests} guest${totalGuests === 1 ? "" : "s"}`;
  }, [search.adults, search.children]);

  const stayText = useMemo(() => {
    const checkIn = new Date(search.checkIn);
    const checkOut = new Date(search.checkOut);
    const nights = Math.max(1, Math.round((checkOut.getTime() - checkIn.getTime()) / (1000 * 60 * 60 * 24)));
    return `${nights} night${nights === 1 ? "" : "s"}`;
  }, [search.checkIn, search.checkOut]);

  const handleSearchSubmit = () => {
    submitAxisRoomsForm(search, { sendToPaymentPage: false });
  };

  const handleRoomBooking = (room: CoralBeachRoom) => {
    submitAxisRoomsForm(search, { room, sendToPaymentPage: true });
  };

  return (
    <div
      className="min-h-screen bg-[#f5efe7] text-slate-950"
      style={{
        backgroundImage:
          "radial-gradient(circle at top left, rgba(21,161,169,0.18), transparent 32%), linear-gradient(180deg, #f5efe7 0%, #f8f4ee 45%, #fcfbf7 100%)",
      }}
    >
      <header className="border-b border-[#15a1a9]/15 bg-[#15a1a9] text-white shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-4 py-4 sm:px-6 xl:px-8">
          <div className="flex items-center gap-4">
            <img
              src={coralBeachBookingSite.logoUrl}
              alt={coralBeachBookingSite.resortName}
              className="h-12 w-auto rounded-xl bg-white/90 px-2 py-1"
            />
            <div className="hidden sm:block">
              <p className="text-sm font-semibold tracking-[0.28em] text-white/80">DIRECT BOOKING</p>
              <p className="text-lg font-semibold">{coralBeachBookingSite.resortName}</p>
            </div>
          </div>
          <div className="hidden items-center gap-5 text-sm font-medium lg:flex">
            <a href={coralBeachBookingSite.websiteUrl} target="_blank" rel="noreferrer" className="transition hover:text-[#f4d3a2]">
              Resort Website
            </a>
            <a href={coralBeachBookingSite.roomsPageUrl} target="_blank" rel="noreferrer" className="transition hover:text-[#f4d3a2]">
              Rooms
            </a>
            <a href={coralBeachBookingSite.whatsappUrl} target="_blank" rel="noreferrer" className="transition hover:text-[#f4d3a2]">
              WhatsApp
            </a>
          </div>
          <Button className="border-0 bg-[#d49c60] text-white hover:bg-[#c48744]" onClick={handleSearchSubmit}>
            Check availability
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8 xl:px-8">
        <section className="overflow-hidden rounded-[2rem] border border-black/5 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.10)]">
          <div className="grid gap-0 xl:grid-cols-[minmax(0,1.2fr)_400px]">
            <div className="relative min-h-[420px] overflow-hidden">
              <img
                src={coralBeachBookingSite.heroImageUrl}
                alt={coralBeachBookingSite.resortName}
                className="absolute inset-0 h-full w-full object-cover"
              />
              <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(7,12,20,0.72),rgba(7,12,20,0.20))]" />
              <div className="relative z-10 flex h-full flex-col justify-between gap-8 p-6 sm:p-8 xl:p-10">
                <div className="space-y-4">
                  <Badge className="w-fit border-0 bg-white/15 px-3 py-1 text-white backdrop-blur">
                    <Waves className="mr-2 h-3.5 w-3.5" />
                    Mahabalipuram beachfront stay
                  </Badge>
                  <div className="space-y-3">
                    <h1 className="max-w-3xl text-4xl font-semibold leading-tight text-white sm:text-5xl">
                      {coralBeachBookingSite.headline}
                    </h1>
                    <p className="max-w-2xl text-sm leading-7 text-white/82 sm:text-base">
                      {coralBeachBookingSite.subheadline}
                    </p>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl border border-white/15 bg-black/20 p-4 text-white backdrop-blur">
                    <p className="text-xs uppercase tracking-[0.2em] text-white/65">Current stay</p>
                    <p className="mt-2 text-lg font-semibold">{stayText}</p>
                    <p className="text-xs text-white/70">
                      {formatReadableDate(search.checkIn)} to {formatReadableDate(search.checkOut)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/15 bg-black/20 p-4 text-white backdrop-blur">
                    <p className="text-xs uppercase tracking-[0.2em] text-white/65">Occupancy</p>
                    <p className="mt-2 text-lg font-semibold">{occupancyText}</p>
                    <p className="text-xs text-white/70">
                      {search.adults} adults {search.children ? `and ${search.children} children` : ""}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/15 bg-black/20 p-4 text-white backdrop-blur">
                    <p className="text-xs uppercase tracking-[0.2em] text-white/65">Rates source</p>
                    <p className="mt-2 text-lg font-semibold">AxisRooms</p>
                    <p className="text-xs text-white/70">Book flow handed off to the live engine</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t border-black/5 bg-[#111827] p-5 text-white xl:border-l xl:border-t-0 sm:p-6">
              <div className="space-y-5">
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-[0.26em] text-[#f4d3a2]">Stay search</p>
                  <h2 className="text-2xl font-semibold">Search Coral Beach availability</h2>
                  <p className="text-sm leading-6 text-white/70">
                    Use your dates and occupancy here. When you continue, the search is handed to the live AxisRooms booking engine with your selected room and dates.
                  </p>
                </div>

                <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="coral-checkin" className="text-white/80">
                        Check-in
                      </Label>
                      <Input
                        id="coral-checkin"
                        type="date"
                        min={formatIsoDate(new Date())}
                        value={search.checkIn}
                        onChange={(event) => {
                          const nextCheckIn = event.target.value;
                          setSearch((current) => {
                            const next = { ...current, checkIn: nextCheckIn };
                            if (next.checkOut <= nextCheckIn) {
                              const checkOut = new Date(nextCheckIn);
                              checkOut.setDate(checkOut.getDate() + 1);
                              next.checkOut = formatIsoDate(checkOut);
                            }
                            return next;
                          });
                        }}
                        className="border-white/15 bg-white text-slate-950"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="coral-checkout" className="text-white/80">
                        Check-out
                      </Label>
                      <Input
                        id="coral-checkout"
                        type="date"
                        min={search.checkIn}
                        value={search.checkOut}
                        onChange={(event) => setSearch((current) => ({ ...current, checkOut: event.target.value }))}
                        className="border-white/15 bg-white text-slate-950"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="coral-adults" className="text-white/80">
                        Adults
                      </Label>
                      <Input
                        id="coral-adults"
                        type="number"
                        min={1}
                        max={4}
                        value={search.adults}
                        onChange={(event) =>
                          setSearch((current) => ({
                            ...current,
                            adults: clamp(Number.parseInt(event.target.value || "1", 10), 1, 4),
                          }))
                        }
                        className="border-white/15 bg-white text-slate-950"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="coral-children" className="text-white/80">
                        Children
                      </Label>
                      <Input
                        id="coral-children"
                        type="number"
                        min={0}
                        max={2}
                        value={search.children}
                        onChange={(event) =>
                          setSearch((current) => ({
                            ...current,
                            children: clamp(Number.parseInt(event.target.value || "0", 10), 0, 2),
                          }))
                        }
                        className="border-white/15 bg-white text-slate-950"
                      />
                    </div>
                    {search.children > 0 ? (
                      <div className="space-y-2">
                        <Label htmlFor="coral-child-age-1" className="text-white/80">
                          Child age 1
                        </Label>
                        <Input
                          id="coral-child-age-1"
                          type="number"
                          min={0}
                          max={17}
                          value={search.childAge1}
                          onChange={(event) =>
                            setSearch((current) => ({
                              ...current,
                              childAge1: clamp(Number.parseInt(event.target.value || "0", 10), 0, 17),
                            }))
                          }
                          className="border-white/15 bg-white text-slate-950"
                        />
                      </div>
                    ) : null}
                    {search.children > 1 ? (
                      <div className="space-y-2">
                        <Label htmlFor="coral-child-age-2" className="text-white/80">
                          Child age 2
                        </Label>
                        <Input
                          id="coral-child-age-2"
                          type="number"
                          min={0}
                          max={17}
                          value={search.childAge2}
                          onChange={(event) =>
                            setSearch((current) => ({
                              ...current,
                              childAge2: clamp(Number.parseInt(event.target.value || "0", 10), 0, 17),
                            }))
                          }
                          className="border-white/15 bg-white text-slate-950"
                        />
                      </div>
                    ) : null}
                  </div>

                  <div className="mt-5 flex flex-col gap-3">
                    <Button className="h-11 border-0 bg-[#d49c60] text-white hover:bg-[#c48744]" onClick={handleSearchSubmit}>
                      Check live availability
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                    <p className="text-xs leading-5 text-white/65">
                      Rates and availability are managed by the live AxisRooms engine for Coral Beach Resort.
                    </p>
                  </div>
                </div>

                <div className="space-y-3 text-sm text-white/80">
                  <div className="flex items-start gap-3">
                    <MapPin className="mt-0.5 h-4 w-4 text-[#f4d3a2]" />
                    <span>{coralBeachBookingSite.address}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <Phone className="h-4 w-4 text-[#f4d3a2]" />
                    <a href={`tel:${coralBeachBookingSite.contactPhone.replace(/\s+/g, "")}`} className="hover:text-white">
                      {coralBeachBookingSite.contactPhone}
                    </a>
                  </div>
                  <div className="flex items-center gap-3">
                    <Mail className="h-4 w-4 text-[#f4d3a2]" />
                    <a href={`mailto:${coralBeachBookingSite.contactEmail}`} className="hover:text-white">
                      {coralBeachBookingSite.contactEmail}
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="mt-6 rounded-[2rem] border border-[#ffcf88]/40 bg-[#fff5e5] px-5 py-4 shadow-sm sm:px-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3 text-[#7b4a15]">
              <Clock3 className="h-5 w-5" />
              <div>
                <p className="font-semibold">Rooms filling fast</p>
                <p className="text-sm">{coralBeachBookingSite.pricingNote}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 text-xs uppercase tracking-[0.18em] text-[#8b5a23]">
              <span className="rounded-full bg-[#ffd8a4] px-3 py-1">AxisRooms handoff</span>
              <span className="rounded-full bg-[#ffd8a4] px-3 py-1">Breakfast plan</span>
              <span className="rounded-full bg-[#ffd8a4] px-3 py-1">Direct booking page</span>
            </div>
          </div>
        </section>

        <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-5">
            {coralBeachBookingSite.rooms.map((room) => (
              <article
                key={room.id}
                className="overflow-hidden rounded-[2rem] border border-black/5 bg-white shadow-[0_22px_60px_rgba(15,23,42,0.08)]"
              >
                <div className="grid gap-0 lg:grid-cols-[340px_minmax(0,1fr)]">
                  <div className="relative min-h-[260px] bg-slate-200">
                    <img src={room.imageUrl} alt={room.marketingName} className="absolute inset-0 h-full w-full object-cover" />
                    <div className="absolute inset-x-0 bottom-0 bg-[linear-gradient(180deg,transparent,rgba(0,0,0,0.70))] p-5 text-white">
                      <p className="text-xs uppercase tracking-[0.3em] text-white/70">{room.planCode} plan</p>
                      <h3 className="mt-2 text-2xl font-semibold">{room.marketingName}</h3>
                    </div>
                  </div>

                  <div className="grid gap-0 border-t border-black/5 lg:grid-cols-[minmax(0,1fr)_250px] lg:border-l lg:border-t-0">
                    <div className="space-y-5 p-5 sm:p-6">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="border-[#15a1a9]/30 bg-[#15a1a9]/5 text-[#127880]">
                          Breakfast included
                        </Badge>
                        <Badge variant="outline" className="border-[#d49c60]/30 bg-[#d49c60]/10 text-[#a46524]">
                          {room.planCode}
                        </Badge>
                      </div>

                      <div className="space-y-3">
                        <h4 className="text-2xl font-semibold text-slate-950">{room.name}</h4>
                        <p className="max-w-3xl text-sm leading-7 text-slate-600">{room.description}</p>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {room.highlights.map((highlight) => (
                          <span
                            key={highlight}
                            className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700"
                          >
                            {highlight}
                          </span>
                        ))}
                      </div>

                      <details className="group rounded-[1.5rem] border border-[#15a1a9]/12 bg-[#f8fbfb] p-4">
                        <summary className="flex cursor-pointer list-none items-center justify-between gap-4">
                          <div>
                            <p className="text-sm font-semibold text-slate-900">View room details</p>
                            <p className="text-xs text-slate-500">Amenities and reference gallery</p>
                          </div>
                          <ArrowRight className="h-4 w-4 text-[#15a1a9] transition group-open:rotate-90" />
                        </summary>
                        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
                          <div>
                            <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Amenities</p>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {room.amenities.map((amenity) => (
                                <span
                                  key={amenity}
                                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-700"
                                >
                                  {amenity}
                                </span>
                              ))}
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            {room.gallery.map((imageUrl) => (
                              <img
                                key={imageUrl}
                                src={imageUrl}
                                alt={room.marketingName}
                                className="h-24 w-full rounded-2xl object-cover"
                              />
                            ))}
                          </div>
                        </div>
                      </details>
                    </div>

                    <div className="border-t border-black/5 bg-[#f7fafb] p-5 lg:border-l lg:border-t-0">
                      <div className="rounded-[1.75rem] border border-[#15a1a9]/12 bg-white p-5 shadow-sm">
                        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">From</p>
                        <p className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
                          {formatCurrency(room.nightlyRate)}
                        </p>
                        <p className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-500">INR / NIGHT</p>
                        <p className="mt-3 text-sm text-slate-600">Reference rate for the current AxisRooms listing.</p>

                        <div className="mt-5 space-y-3 text-sm text-slate-600">
                          <div className="flex items-start gap-2">
                            <CheckCircle2 className="mt-0.5 h-4 w-4 text-[#15a1a9]" />
                            <span>Breakfast included</span>
                          </div>
                          <div className="flex items-start gap-2">
                            <ShieldCheck className="mt-0.5 h-4 w-4 text-[#15a1a9]" />
                            <span>Live confirmation happens in AxisRooms checkout</span>
                          </div>
                          <div className="flex items-start gap-2">
                            <Users className="mt-0.5 h-4 w-4 text-[#15a1a9]" />
                            <span>{occupancyText} selected for handoff</span>
                          </div>
                        </div>

                        <div className="mt-6 space-y-2">
                          <Button className="w-full border-0 bg-[#15a1a9] text-white hover:bg-[#118991]" onClick={() => handleRoomBooking(room)}>
                            Book now
                            <ArrowRight className="ml-2 h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            className="w-full border-[#d49c60]/35 bg-[#fff5e8] text-[#9d5f1f] hover:bg-[#ffedd1]"
                            onClick={handleSearchSubmit}
                          >
                            Check availability
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="space-y-4 xl:sticky xl:top-6">
            <Card className="rounded-[2rem] border border-black/5 bg-[#111827] text-white shadow-[0_22px_60px_rgba(15,23,42,0.12)]">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-white">
                  <Sparkles className="h-5 w-5 text-[#f4d3a2]" />
                  Coral Beach direct-booking notes
                </CardTitle>
                <CardDescription className="text-white/70">
                  This host is prepared as a client-specific branded booking surface.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm text-white/80">
                <div className="flex items-start gap-3">
                  <CalendarDays className="mt-0.5 h-4 w-4 text-[#f4d3a2]" />
                  <span>
                    Selected stay: {formatReadableDate(search.checkIn)} to {formatReadableDate(search.checkOut)}
                  </span>
                </div>
                <div className="flex items-start gap-3">
                  <Users className="mt-0.5 h-4 w-4 text-[#f4d3a2]" />
                  <span>
                    Occupancy sent to AxisRooms: {search.adults} adult(s)
                    {search.children ? `, ${search.children} child(ren)` : ""}
                  </span>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-[#f4d3a2]" />
                  <span>Complimentary breakfast is included with Coral Beach room bookings.</span>
                </div>
                <div className="flex items-start gap-3">
                  <Waves className="mt-0.5 h-4 w-4 text-[#f4d3a2]" />
                  <span>Rooms, descriptions, media, and rate references are mapped from Coral Beach Resort public pages and AxisRooms.</span>
                </div>
              </CardContent>
            </Card>

            <Card className="rounded-[2rem] border border-black/5 bg-white shadow-sm">
              <CardHeader>
                <CardTitle>Need help booking?</CardTitle>
                <CardDescription>Use the direct Coral Beach contact points.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <a
                  href={`tel:${coralBeachBookingSite.contactPhone.replace(/\s+/g, "")}`}
                  className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 transition hover:border-[#15a1a9]/35 hover:bg-[#f8fbfb]"
                >
                  <Phone className="h-4 w-4 text-[#15a1a9]" />
                  <span>{coralBeachBookingSite.contactPhone}</span>
                </a>
                <a
                  href={`mailto:${coralBeachBookingSite.contactEmail}`}
                  className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 transition hover:border-[#15a1a9]/35 hover:bg-[#f8fbfb]"
                >
                  <Mail className="h-4 w-4 text-[#15a1a9]" />
                  <span>{coralBeachBookingSite.contactEmail}</span>
                </a>
                <a
                  href={coralBeachBookingSite.whatsappUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 transition hover:border-[#15a1a9]/35 hover:bg-[#f8fbfb]"
                >
                  <MessageBubble />
                  <span>WhatsApp Coral Beach reservations</span>
                </a>
              </CardContent>
            </Card>
          </div>
        </section>
      </main>
    </div>
  );
};

export default CoralBeachBooking;
