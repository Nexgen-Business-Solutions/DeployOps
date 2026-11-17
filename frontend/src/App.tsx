import { Loader2 } from "lucide-react";
import { useEffect, useMemo } from "react";
import { createBrowserRouter, createRoutesFromElements, RouterProvider, Navigate, Route } from "react-router";

import Builder from "./builder/Builder";
import FormsList from "./builder/FormsList";
import { isDesigner } from "./builder/api";
import AppShell from "./components/AppShell";
import { Banner } from "./components/ui";
import { logout } from "./lib/api";
import { SessionContext } from "./lib/session";
import type { Me } from "./lib/types";
import { APP_BASE } from "./lib/paths";
import { useApi } from "./lib/useApi";
import CardJobs from "./pages/CardJobs";
import ChangePassword from "./pages/ChangePassword";
import Form from "./pages/Form";
import Submission from "./pages/Submission";
import FillForm from "./pages/FillForm";
import Home from "./pages/Home";
import Job from "./pages/Job";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import { isFillPath, outsideFill } from "./pages/fillRoutes";

function sessionUser(): string | undefined {
    const match = document.cookie.match(/(?:^|;\s*)user_id=([^;]*)/);
    const user = match ? decodeURIComponent(match[1]) : "Guest";
    return user && user !== "Guest" ? user : undefined;
}

export default function App() {
    // Share links work without a DeployOps role (or any login): their own router, no app shell.
    return isFillPath(window.location.pathname) ? <FillRouter /> : <SignedInApp />;
}

function FillRouter() {
    const router = useMemo(() => createBrowserRouter(createRoutesFromElements(
        <>
            <Route path="/f/:form" element={<FillForm />} />
            <Route path="/f/:form/entry/:name" element={<Submission bare />} />
            <Route path="*" element={<LeaveFill />} />
        </>
    ), {basename: APP_BASE}), []);
    return <RouterProvider router={router} />;
}

function LeaveFill() {
    useEffect(() => {window.location.assign(outsideFill());}, []);
    return null;
}

function SignedInApp() {
    const { data: me, error, loading } = useApi<Me>("deployops.api.technician.me");

    async function signOut() {
        try {
            await logout();
        } finally {
            window.location.assign(APP_BASE);
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

    return <SessionContext.Provider value={me}><SessionRouter me={me} signOut={signOut} /></SessionContext.Provider>;
}

function SessionRouter({me, signOut}: {me: Me; signOut: () => Promise<void>}) {
    const router = useMemo(() => createBrowserRouter(createRoutesFromElements(
        <>
            {!me.suite && <Route path="/" element={<Home onLogout={signOut} />} />}
            <Route element={<AppShell suite={me.suite} onLogout={signOut} />}>
                {me.suite && <Route index element={<Overview />} />}
                <Route path="/c/:card" element={<CardJobs />} />
                <Route path="/job/:job" element={<Job />} />
                <Route path="/form/:doctype/:name" element={<Form />} />
                <Route path="/s/:name" element={<Submission />} />
                {isDesigner(me.roles, me.user) && <><Route path="/builder" element={<FormsList />} /><Route path="/builder/:form" element={<Builder />} /></>}
                <Route path="/password" element={<ChangePassword />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
        </>
    ), {basename: APP_BASE}), [me, signOut]);
    return <RouterProvider router={router} />;
}
