import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// Nullable: createClient() throws synchronously on an empty URL, which would crash the whole
// app (including pages that have nothing to do with Supabase) before it's configured. Module
// pages that need it should check for null and show their own "not configured" state.
export const supabase: SupabaseClient | null = url && anonKey ? createClient(url, anonKey) : null;

if (!supabase) {
  console.warn(
    'VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY not configured — module pages that read/write ' +
      'shared data (e.g. Schedule) will not work until these are set.'
  );
}
