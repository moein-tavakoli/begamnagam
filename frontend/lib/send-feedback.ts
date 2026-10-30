export type SendFeedback = "accepted" | "uncertain" | "rejected";

// A successful queue admission is not a delivery receipt.
export function sendFeedback(status: string): SendFeedback {
  if (["failed", "blocked", "cancelled", "refunded"].includes(status)) return "rejected";
  if (["paid", "queued", "processing", "sending", "accepted", "sent", "delivered", "simulated", "delivered_demo"].includes(status)) return "accepted";
  return "uncertain";
}
