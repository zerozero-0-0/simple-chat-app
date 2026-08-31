import type { Message, Room, User } from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** 呼び出し側が状態で分岐できるよう、HTTP のステータスを持たせる。 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}/api${path}`, {
    // セッションは HttpOnly Cookie なので、明示的に送る
    credentials: "include",
    headers:
      init.body === undefined ? {} : { "content-type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // 本文が JSON とは限らない
  }
  return `${response.status} ${response.statusText}`;
}

export function signUp(loginName: string, displayName?: string): Promise<User> {
  return request<User>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ login_name: loginName, display_name: displayName }),
  });
}

export function logIn(loginName: string): Promise<User> {
  return request<User>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ login_name: loginName }),
  });
}

export function logOut(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
}

export function fetchMe(): Promise<User> {
  return request<User>("/auth/me");
}

export function fetchRooms(): Promise<Room[]> {
  return request<Room[]>("/rooms");
}

/** 部屋に入る。何度呼んでも同じ結果になる。 */
export function joinRoom(publicId: string): Promise<Room> {
  return request<Room>(`/rooms/${publicId}/members`, { method: "POST" });
}

/** `after` より後のメッセージを古い順に返す。 */
export function fetchMessages(
  publicId: string,
  after?: number,
): Promise<Message[]> {
  const query = after === undefined ? "" : `?after=${after}`;
  return request<Message[]>(`/rooms/${publicId}/messages${query}`);
}

export function sendMessage(
  publicId: string,
  clientMessageId: string,
  body: string,
): Promise<Message> {
  return request<Message>(`/rooms/${publicId}/messages`, {
    method: "POST",
    body: JSON.stringify({ client_message_id: clientMessageId, body }),
  });
}

/** 新しいメッセージを受け取る WebSocket の URL。 */
export function messageStreamUrl(publicId: string): string {
  const url = new URL(`${BASE_URL}/api/rooms/${publicId}/messages/stream`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
