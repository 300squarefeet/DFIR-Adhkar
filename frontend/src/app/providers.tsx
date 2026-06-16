import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { useState } from "react";

import { AuthProvider } from "@/lib/auth";
import { ToastProvider } from "@/ui/Toast";

import { router } from "./routes";

export function Providers() {
  const [qc] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false } } }));
  return (
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
