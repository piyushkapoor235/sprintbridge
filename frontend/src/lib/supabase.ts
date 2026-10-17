import { createClient } from "@supabase/supabase-js";
const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
export const configured = Boolean(
  url && key && import.meta.env.VITE_API_BASE_URL,
);
export const supabase = url && key ? createClient(url, key) : null;
