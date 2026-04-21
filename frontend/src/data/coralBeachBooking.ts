export type CoralBeachRoom = {
  id: string;
  roomId: string;
  ratePlanId: string;
  name: string;
  marketingName: string;
  nightlyRate: number;
  planCode: string;
  imageUrl: string;
  description: string;
  highlights: string[];
  amenities: string[];
  gallery: string[];
};

export const coralBeachBookingSite = {
  hostnames: ["bookings.coralbeachresort.in"],
  resortName: "Coral Beach Resort",
  logoUrl: "https://coralbeachresort.in/assets/images/Logo%20%20Corallogo.png",
  heroImageUrl: "https://coralbeachresort.in/assets/gallery/banner.png",
  websiteUrl: "https://coralbeachresort.in/",
  roomsPageUrl: "https://coralbeachresort.in/rooms/",
  directBookingUrl:
    "https://app.axisrooms.com/beV2/displaySearchResultV3.html?applicableDealId=0&room_number=0&login=false&allHotels=true&searcherId=55934112&searchNumber=1",
  contactEmail: "res@coralbeach.in",
  contactPhone: "+91 9444 333 333",
  whatsappUrl: "https://wa.me/919444333333",
  address: "Old No. 62, New No. 109, ECR Road, Mahabalipuram, Chennai, Tamil Nadu - 603104",
  axisRooms: {
    productId: "197326",
    bookingEngineId: "4730",
    searcherId: "55934112",
    searchNumber: "1",
    applicableDealId: "0",
  },
  headline: "Book your stay at Coral Beach Resort",
  subheadline:
    "A Coral Beach booking experience tailored for direct reservations, with the room mix and current AxisRooms tariffs mapped into a cleaner branded surface.",
  pricingNote:
    "Reference rates below were captured from the live AxisRooms listing on March 21, 2026. Final live pricing and availability are confirmed during checkout.",
  rooms: [
    {
      id: "deluxe",
      roomId: "72108",
      ratePlanId: "47787",
      name: "Deluxe",
      marketingName: "Deluxe Room",
      nightlyRate: 11800,
      planCode: "CP",
      imageUrl: "https://coralbeachresort.in/assets/gallery/Deluxe%20Rooms.png",
      description:
        "A spacious, well-appointed room featuring a comfortable bed, modern amenities, free Wi-Fi, TV, and a private bathroom for a cozy and convenient stay.",
      highlights: ["Breakfast included", "Ideal for couples", "Fast Wi-Fi"],
      amenities: [
        "Hairdryer",
        "Toiletries",
        "Towels",
        "TV",
        "Air Conditioning",
        "Iron / Ironing Board",
        "Kettle",
        "Wifi",
        "Bathroom",
        "Housekeeping",
        "In-room dining",
        "Room service",
      ],
      gallery: [
        "https://s3-ap-southeast-1.amazonaws.com/resources.axisrooms/static/hotels/176061/E65A8151.JPG",
        "https://s3-ap-southeast-1.amazonaws.com/resources.axisrooms/static/hotels/176061/E65A8188.JPG",
        "https://s3-ap-southeast-1.amazonaws.com/resources.axisrooms/static/hotels/176061/E65A8192.JPG",
      ],
    },
    {
      id: "deluxe-family-suite",
      roomId: "72110",
      ratePlanId: "47787",
      name: "Deluxe Family Suite",
      marketingName: "Deluxe Family Suite",
      nightlyRate: 15340,
      planCode: "CP",
      imageUrl: "https://coralbeachresort.in/assets/gallery/Deluxe%20Rooms.png",
      description:
        "Experience exceptional comfort in our Family Suite Room, thoughtfully crafted for families seeking extra space and luxury. The suite includes a spacious bedroom, an inviting living area, premium bedding, high-speed Wi-Fi, TV, tea and coffee facilities, and an elegantly designed bathroom with premium toiletries.",
      highlights: ["Family layout", "Lounge space", "Breakfast included"],
      amenities: [
        "Hairdryer",
        "Hot & Cold Water",
        "Toiletries",
        "Towels",
        "TV",
        "Air Conditioning",
        "Mineral Water",
        "Wifi",
        "Bathroom",
        "Room service",
      ],
      gallery: ["https://coralbeachresort.in/assets/gallery/Deluxe%20Rooms.png"],
    },
    {
      id: "garden-club-room",
      roomId: "72114",
      ratePlanId: "47787",
      name: "Garden Club Room",
      marketingName: "Garden Club Room",
      nightlyRate: 16520,
      planCode: "CP",
      imageUrl: "https://coralbeachresort.in/assets/gallery/Club%20Suite.png",
      description:
        "The Garden Club Room offers a relaxing stay with direct access or views to lush garden surroundings, plus tasteful interiors, complimentary Wi-Fi, TV, tea and coffee amenities, and a well-appointed bathroom.",
      highlights: ["Garden-facing", "Premium club feel", "Best for longer stays"],
      amenities: [
        "Hairdryer",
        "Hot & Cold Water",
        "Toiletries",
        "TV",
        "Air Conditioning",
        "Iron / Ironing Board",
        "Kettle",
        "Mineral Water",
        "Safe",
        "Bathroom",
        "Work Desk",
      ],
      gallery: ["https://coralbeachresort.in/assets/gallery/Club%20Suite.png"],
    },
    {
      id: "premium-suite",
      roomId: "72111",
      ratePlanId: "47787",
      name: "Premium Suite",
      marketingName: "Premium Suite",
      nightlyRate: 31860,
      planCode: "CP",
      imageUrl: "https://s3-ap-southeast-1.amazonaws.com/resources.axisrooms/static/hotels/176061/Premium%20Suite%20(3).jpeg",
      description:
        "Experience refined luxury in our Premium Suite, designed with sophisticated decor and generous space for ultimate relaxation. The suite features a plush bedroom, an elegant living area, high-speed Wi-Fi, smart TV, premium tea and coffee amenities, and an upscale bathroom with premium toiletries.",
      highlights: ["Signature suite", "Large-format stay", "Premium interiors"],
      amenities: [
        "Toiletries",
        "Hot & Cold Water",
        "TV",
        "Air Conditioning",
        "Private Bathroom",
        "Housekeeping",
        "Room service",
        "Closet",
        "Charging points",
        "Seating area",
      ],
      gallery: [
        "https://s3-ap-southeast-1.amazonaws.com/resources.axisrooms/static/hotels/176061/Premium%20Suite%20(3).jpeg",
        "https://s3-ap-southeast-1.amazonaws.com/resources.axisrooms/static/hotels/176061/Premium%20Suite%20(4).jpeg",
        "https://s3-ap-southeast-1.amazonaws.com/resources.axisrooms/static/hotels/176061/Premium%20Suite%20(5).jpeg",
        "https://s3-ap-southeast-1.amazonaws.com/resources.axisrooms/static/hotels/176061/Premium%20Suite%20(6).jpeg",
      ],
    },
  ] satisfies CoralBeachRoom[],
} as const;
