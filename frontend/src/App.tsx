import { Loader2 } from "lucide-react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { Banner } from "./components/ui";
import { logout } from "./lib/api";
import { SessionContext } from "./lib/session";
import type { Me } from "./lib/types";
import { useApi } from "./lib/useApi";
import CardJobs from "./pages/CardJobs";
import Form from "./pages/Form";
import Home from "./pages/Home";
import Job from "./pages/Job";
import Login from "./pages/Login";

function sessionUser(): string | undefined {
    const match = document.cookie.match(/(?:^|;\s*)user_id=([^;]*)/);
    const user = match ? decodeURIComponent(match[1]) : "Guest";
    return user && user !== "Guest" ? user : undefined;
}

export default function App() {
    const { data: me, error, loading } = useApi<Me>("deployops.api.technician.me");

    async function signOut() {
        try {
            await logout();
        } finally {
            window.location.assign("/");
        }
    }

    if (loading && !me) {
        return (
            <div className="grid min-h-svh place-items-center">
                <Loader2 className="size-6 animate-spin text-zinc-300" aria-label="Loading" />
            </div>
        );
    }

    if (!me) {
        if (error && error.status !== 403 && error.status !== 401) {
            return (
                <div className="mx-auto max-w-md p-6">
                    <Banner>{error.message}</Banner>
                </div>
            );
        }
        return <Login signedInAs={sessionUser()} />;
    }

    return (
        <SessionContext.Provider value={me}>
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<Home onLogout={signOut} />} />
                    <Route path="/c/:card" element={<CardJobs />} />
                    <Route path="/job/:job" element={<Job />} />
                    <Route path="/form/:doctype/:name" element={<Form />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </BrowserRouter>
        </SessionContext.Provider>
    );
}
