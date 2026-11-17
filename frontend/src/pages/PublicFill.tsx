// A public form opened without a login: fill in the browser, send once, see a thank-you.
import { CheckCircle2, ClipboardList, Send } from "lucide-react";
import { useState } from "react";
import { Banner, Button, Page } from "../components/ui";
import { FormRenderer } from "../forms/FormRenderer";
import { checkComplete, errorsByField } from "../forms/logic";
import { clearDraft, loadDraft, saveDraft, sendPublic } from "../forms/publicFill";
import type { Answers, Definition, FormError, ScreenReference } from "../forms/types";
import { UploadTracker } from "../forms/uploads";
import { ApiError, uploadTo } from "../lib/api";

export type PublicInfo = {
	name: string; title: string; subtitle: string | null;
	audience: "Public" | "Roles" | "Users"; entry_limit: "Multiple" | "Once";
	login_required: boolean; can_start: boolean; reason: string | null;
	mine: {name: string; status: string; created: string; modified: string}[];
	definition?: Definition; references?: ScreenReference[];
};

function Header({title, subtitle}: {title: string; subtitle?: string | null}) {
	return <header className="flex items-start gap-4">
		<span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-600"><ClipboardList className="size-6" /></span>
		<div><h1 className="text-2xl font-semibold tracking-tight">{title}</h1>{subtitle && <p className="mt-1 text-muted">{subtitle}</p>}</div>
	</header>;
}

export function ThankYou({title}: {title: string}) {
	return <Page><div className="space-y-6"><Header title={title} />
		<div className="flex items-center gap-3 rounded-2xl bg-emerald-50 p-5 text-emerald-800 ring-1 ring-emerald-200"><CheckCircle2 className="size-6 shrink-0" /><p className="font-medium">Thank you, your answers were sent.</p></div>
	</div></Page>;
}

export function PublicFill({info}: {info: PublicInfo}) {
	const [answers, setAnswers] = useState<Answers>(() => loadDraft(info.name));
	const [problems, setProblems] = useState<FormError[]>([]), [message, setMessage] = useState("");
	const [busy, setBusy] = useState(false), [sent, setSent] = useState(false), [uploading, setUploading] = useState(0);
	const [uploads] = useState(() => new UploadTracker(setUploading));

	if (sent) return <ThankYou title={info.title} />;
	if (!info.can_start || !info.definition) return <Page><div className="space-y-6"><Header title={info.title} subtitle={info.subtitle} /><Banner kind="warning">{info.reason ?? "This form isn't open."}</Banner></div></Page>;
	const definition = info.definition;

	function change(id: string, value: unknown) {
		setAnswers(current => {const next = {...current, [id]: value}; saveDraft(info.name, next); return next;});
	}
	async function upload(file: Blob, filename: string, fieldId?: string) {
		const out = await uploads.run(() => uploadTo<{file_url: string}>("forms_core.api.upload_public", file, filename, {form: info.name, field: fieldId ?? ""}));
		return out.file_url;
	}
	async function send() {
		setMessage(""); setBusy(true);
		await uploads.wait();
		const missing = checkComplete(definition, answers);
		if (missing.length) {setProblems(missing); setBusy(false); return;}
		try {
			await sendPublic(info.name, answers);
			clearDraft(info.name); setSent(true);
		} catch (e) {
			if (e instanceof ApiError && e.formErrors) setProblems(e.formErrors);
			setMessage(e instanceof Error ? e.message : String(e));
			setBusy(false);
		}
	}

	const mapped = errorsByField(definition, problems, answers);
	return <Page className="pb-28"><div className="space-y-6">
		<Header title={info.title} subtitle={info.subtitle} />
		{info.entry_limit === "Once" && <Banner kind="info">You can send this form once.</Banner>}
		{mapped.byField.size > 0 && <Banner>{mapped.byField.size} answers still needed.</Banner>}
		{mapped.general.map((m, i) => <Banner key={i}>{m}</Banner>)}
		{message && mapped.byField.size === 0 && <Banner>{message}</Banner>}
	</div>
		<FormRenderer definition={definition} answers={answers} errors={mapped.byField} references={info.references ?? []} ctx={{mode: "fill", values: {}, upload}} onChange={change} />
		<div className="mt-10"><Button className="w-full sm:w-auto" loading={busy} disabled={uploading > 0} icon={<Send className="size-4" />} onClick={() => void send()}>{uploading > 0 ? "Uploading…" : "Send"}</Button></div>
	</Page>;
}
