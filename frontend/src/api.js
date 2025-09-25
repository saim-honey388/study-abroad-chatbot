import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

export async function startSession(name, phone, email) {
  const res = await api.post("/api/start", { name, phone, email });
  return res.data;
}

export async function sendMessage(sessionId, text) {
  const res = await api.post("/api/message", { session_id: sessionId, text });
  return res.data;
}

export async function uploadDocument(sessionId, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post(`/api/upload-document?session_id=${sessionId}`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}


