import { api } from "@/lib/api";

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024;

type PresignResponse = {
  upload_url: string;
  fields: Record<string, string>;
  public_url: string;
};

export function validateImageFile(file: File): string | null {
  if (!ALLOWED_TYPES.includes(file.type)) {
    return "Only JPEG, PNG, or WEBP images are allowed";
  }
  if (file.size > MAX_BYTES) {
    return "Image must be under 5MB";
  }
  return null;
}

export async function uploadImage(
  file: File,
  context: "room" | "hero",
  roomId?: string
): Promise<string> {
  const presign = await api.post<PresignResponse>("/api/media/presign", {
    context,
    room_id: roomId,
    filename: file.name,
    content_type: file.type,
  });

  const formData = new FormData();
  Object.entries(presign.fields).forEach(([key, value]) => formData.append(key, value));
  formData.append("file", file);

  const res = await fetch(presign.upload_url, { method: "POST", body: formData });
  if (!res.ok) {
    throw new Error(`Upload failed: HTTP ${res.status}`);
  }

  return presign.public_url;
}
