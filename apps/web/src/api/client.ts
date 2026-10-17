import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";

const TOKEN_KEY = "schemawatch_bearer_token";

export function getStoredToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // ignore
  }
}

export function removeStoredToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

// Middleware for Bearer Token injection and 401 handling
const authMiddleware: Middleware = {
  async onRequest({ request }) {
    const token = getStoredToken();
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
  async onResponse({ response }) {
    if (response.status === 401) {
      removeStoredToken();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("schemawatch:unauthorized"));
      }
    }
    return response;
  },
};

const getBaseUrl = (): string => {
  if (
    typeof window !== "undefined" &&
    window.location &&
    window.location.origin &&
    window.location.origin !== "null"
  ) {
    return window.location.origin;
  }
  return "http://localhost:8000";
};

export const apiClient = createClient<paths>({
  baseUrl: getBaseUrl(),
  fetch: (input: Request): Promise<Response> => fetch(input),
});

apiClient.use(authMiddleware);

// Typed API Helpers

export async function fetchStats() {
  const { data, error } = await apiClient.GET("/api/stats");
  if (error || !data) {
    throw new Error(error ? JSON.stringify(error) : "Failed to fetch stats");
  }
  return data;
}

export async function fetchConfig() {
  const { data, error } = await apiClient.GET("/api/config");
  if (error || !data) {
    throw new Error(error ? JSON.stringify(error) : "Failed to fetch config");
  }
  return data;
}

export async function fetchEndpoints(params?: { cursor?: number; limit?: number }) {
  const { data, error } = await apiClient.GET("/api/endpoints", {
    params: {
      query: {
        cursor: params?.cursor,
        limit: params?.limit ?? 50,
      },
    },
  });
  if (error || !data) {
    throw new Error(error ? JSON.stringify(error) : "Failed to fetch endpoints");
  }
  return data;
}

export async function fetchEndpointById(id: number) {
  const { data, error } = await apiClient.GET("/api/endpoints/{id}", {
    params: {
      path: { id },
    },
  });
  if (error || !data) {
    throw new Error(error ? JSON.stringify(error) : `Endpoint #${id} not found`);
  }
  return data;
}

export async function fetchEndpointBaseline(id: number) {
  const { data, error } = await apiClient.GET("/api/endpoints/{id}/baseline", {
    params: {
      path: { id },
    },
  });
  if (error || !data) {
    throw new Error(error ? JSON.stringify(error) : `Baseline for #${id} not found`);
  }
  return data;
}

export async function acceptEndpointBaseline(id: number) {
  const { data, error } = await apiClient.POST("/api/endpoints/{id}/accept", {
    params: {
      path: { id },
    },
  });
  if (error || !data) {
    throw new Error(error ? JSON.stringify(error) : `Failed to accept baseline for #${id}`);
  }
  return data;
}

export async function fetchEvents(params?: {
  severity?: "breaking" | "warning" | "info";
  vendor?: string;
  endpoint_id?: number;
  acknowledged?: boolean;
  since?: string;
  cursor?: number;
  limit?: number;
}) {
  const { data, error } = await apiClient.GET("/api/events", {
    params: {
      query: {
        severity: params?.severity,
        vendor: params?.vendor,
        endpoint_id: params?.endpoint_id,
        acknowledged: params?.acknowledged,
        since: params?.since,
        cursor: params?.cursor,
        limit: params?.limit ?? 50,
      },
    },
  });
  if (error || !data) {
    throw new Error(error ? JSON.stringify(error) : "Failed to fetch events");
  }
  return data;
}

export async function acknowledgeEvent(id: number) {
  const { data, error } = await apiClient.POST("/api/events/{id}/ack", {
    params: {
      path: { id },
    },
  });
  if (error || !data) {
    throw new Error(error ? JSON.stringify(error) : `Failed to acknowledge event #${id}`);
  }
  return data;
}

export async function unacknowledgeEvent(id: number) {
  const { data, error } = await apiClient.POST("/api/events/{id}/unack", {
    params: {
      path: { id },
    },
  });
  if (error || !data) {
    throw new Error(error ? JSON.stringify(error) : `Failed to reopen event #${id}`);
  }
  return data;
}
