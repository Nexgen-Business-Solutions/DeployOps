// A job machine's v2 forms (planned by Form Rules): start, continue or view each one.
import { Check, ChevronRight, Flag, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import type { MachineFormEntry, MachineFormsView } from "../forms/types";
import { post } from "../lib/api";
import { useApi } from "../lib/useApi";
import { Banner } from "./ui";

export function MachineForms({job, row, onLoaded}: {job: string; row: string; onLoaded?: (usesForms: boolean) => void}) {
	const {data, error} = useApi<MachineFormsView>("deployops.api.forms.machine_forms", {job, row});
	const navigate = useNavigate();
	const [busy, setBusy] = useState(""), [startError, setStartError] = useState("");
	const uses = data?.uses_forms;
	useEffect(() => {if (uses !== undefined) onLoaded?.(uses);}, [uses, onLoaded]);
	if (error) return <div className="mt-3"><Banner>{error.message}</Banner></div>;
	if (!data?.uses_forms) return null;
	async function open(entry: MachineFormEntry) {
		if (entry.submission && entry.status !== "Not started") {navigate(`/s/${encodeURIComponent(entry.submission)}`); return;}
		setBusy(entry.form); setStartError("");
		try {
			const out = await post<{submission: string}>("deployops.api.forms.start_machine_form", {job, row, form: entry.form});
			navigate(`/s/${encodeURIComponent(out.submission)}`);
		} catch (e) {setStartError(e instanceof Error ? e.message : String(e)); setBusy("");}
	}
	return <div className="mt-3 space-y-2">
		{data.forms.map(entry => {
			const done = entry.status === "Submitted", started = entry.status === "Draft";
			const actionable = done || started || entry.can_start;
			const label = done ? "View" : started ? "Continue" : entry.can_start ? "Start" : "Not available";
			return <button key={entry.form} type="button" disabled={!actionable || !!busy} onClick={() => void open(entry)}
				className="group flex w-full items-center gap-3 rounded-2xl bg-zinc-50 px-4 py-3 text-left transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60">
				<span className={`grid size-6 shrink-0 place-items-center rounded-full ${done ? "bg-emerald-500 text-white" : started ? "border-2 border-brand-500" : "border-2 border-dashed border-zinc-300"}`}>{done && <Check className="size-3.5" strokeWidth={3} />}</span>
				<span className="min-w-0 flex-1">
					<span className="block truncate text-[15px] font-medium">{entry.title}</span>
					<span className="flex items-center gap-1.5 text-xs text-muted">{entry.status}{entry.required ? " · required" : " · optional"}{entry.flagged && <span className="inline-flex items-center gap-0.5 text-amber-700"><Flag className="size-3" />flagged</span>}</span>
				</span>
				{busy === entry.form ? <Loader2 className="size-4 animate-spin text-muted" /> : <span className={`text-sm font-medium ${actionable ? "text-brand-600" : "text-muted"}`}>{label}</span>}
				{actionable && <ChevronRight className="size-[18px] text-zinc-300 group-hover:text-ink" />}
			</button>;
		})}
		{startError && <Banner>{startError}</Banner>}
	</div>;
}
