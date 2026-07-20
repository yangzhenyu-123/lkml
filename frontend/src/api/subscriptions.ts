import { apiClient } from "./client";
import type { Subscription, SubscriptionCreate } from "@/types";

export const subscriptionsApi = {
  list: () =>
    apiClient.get<{ items: Subscription[] }>("/subscriptions").then((r) => r.data),
  create: (data: SubscriptionCreate) =>
    apiClient.post<Subscription>("/subscriptions", data).then((r) => r.data),
  remove: (id: number) => apiClient.delete(`/subscriptions/${id}`).then((r) => r.data),
};
