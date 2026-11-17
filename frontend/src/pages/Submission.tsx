import { UploadTracker } from "../forms/uploads";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { FileDown, Plus } from "lucide-react";

const pdfUrl = (name: string, audience: "internal" | "customer") => `/api/method/deployops.api.forms.submission_pdf?name=${encodeURIComponent(name)}&audience=${audience}`;
import { DocumentsDock } from "../components/form/DocumentsDock";
import { ActionDialog, Banner, Button, Page, Skeleton, TopBar } from "../components/ui";
import { FormRenderer } from "../forms/FormRenderer";
import { checkComplete, errorsByField, fixedRowSeeds, progress, screenHeader, topFieldOf } from "../forms/logic";
import { AnswerQueue, mergeSaved, type SaveState } from "../forms/queue";
import { toDocuments } from "../forms/references";
import type { Answers, FormError, SubmissionView } from "../forms/types";
import { ApiError, post, uploadPrivateFile } from "../lib/api";
import { useApi } from "../lib/useApi";
import { APP_BASE } from "../lib/paths";
import { entryPath } from "./fillRoutes";
/** `bare`: opened from a share link (/f/<form>/entry/<name>), outside the signed-in app shell. */
export default function Submission({ bare = false }: { bare?: boolean }) {
	const { name = "" } = useParams();
	const { data, error, loading, reload } = useApi<SubmissionView>("forms_core.api.get_submission", { name });
	const shareEntry = !!data && data.name === name && !data.context_doctype;
	useEffect(() => {
		// A share-form entry lives under its share link, which the app shell's router doesn't serve.
		if (shareEntry && !bare && data) window.location.replace(`${APP_BASE}${entryPath(data.form, data.name)}`);
	}, [shareEntry, bare, data]);
	if (!data || data.name !== name || (shareEntry && !bare))
		return <><TopBar title="Form" back="/" /><Page>{error ? <Banner>{error.message}</Banner> : loading || shareEntry ? <Skeleton /> : null}</Page></>;
	return <LoadedSubmission key={`${data.name}-${data.docstatus}`} data={data} reload={reload} bare={bare} />;
}
function LoadedSubmission({ data, reload, bare }: {
	data: SubmissionView;
	reload: () => Promise<void>;
	bare: boolean;
}) {
	const editable = data.can_write && data.docstatus === 0;
	const [values, setValues] = useState<Answers>(() => ({ ...data.answers, ...(editable ? fixedRowSeeds(data.definition, data.answers) : {}) }));
	const valuesRef = useRef(values);
	const [problems, setProblems] = useState<FormError[]>([]), [saveState, setSaveState] = useState<SaveState>("idle"), [saveError, setSaveError] = useState<ApiError | null>(null);
	const [confirmOpen, setConfirmOpen] = useState(false), [submitting, setSubmitting] = useState(false), [submitError, setSubmitError] = useState<string | null>(null);
	const queueRef = useRef<AnswerQueue | null>(null);
	const [uploadCount, setUploadCount] = useState(0);
	const [uploads] = useState(() => new UploadTracker(setUploadCount));
	useEffect(() => {
		if (!editable)
			return;
		let active = true;
		const queue = new AnswerQueue({
			save: changes => post<Answers>("forms_core.api.save_answers", { name: data.name, changes }, { keepalive: true }), fieldOf: id => topFieldOf(data.definition, id), onSaved: (server, pending) => {
				if (active) {
					const next = mergeSaved(server, pending);
					valuesRef.current = next;
					setValues(next);
				}
			}, onState: (state, error) => {
				if (active) {
					setSaveState(state);
					setSaveError(error);
					if (error?.formErrors)
						setProblems(error.formErrors);
				}
			}
		});
		queueRef.current = queue;
		for (const [id, v] of Object.entries(fixedRowSeeds(data.definition, data.answers)))
			queue.change(id, v);
		const leave = () => queue.dispose(), online = () => void queue.flush(), unload = (e: BeforeUnloadEvent) => {
			if (Object.keys(queue.pending).length) {
				e.preventDefault();
				e.returnValue = "";
			}
		};
		window.addEventListener("pagehide", leave);
		window.addEventListener("beforeunload", unload);
		window.addEventListener("online", online);
		return () => { active = false; queue.dispose(); queueRef.current = null; window.removeEventListener("pagehide", leave); window.removeEventListener("beforeunload", unload); window.removeEventListener("online", online); };
	}, [data, editable]);
	function change(id: string, value: unknown) {
		if (!editable || !queueRef.current)
			return; const changed = { ...valuesRef.current, [id]: value }; const seeds = fixedRowSeeds(data.definition, changed); const next = { ...changed, ...seeds }; valuesRef.current = next; setValues(next); queueRef.current.change(id, value); for (const [key, v] of Object.entries(seeds))
			queueRef.current.change(key, v); setProblems(current => current.filter(e => !e.field || topFieldOf(data.definition, e.field) !== id));
	}
	function showErrors(errors: FormError[]) {
		setProblems(errors); const first = errors.find(e => e.field)?.field; if (first) {
			const id = topFieldOf(data.definition, first);
			document.getElementById(`f-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
		}
	}
	async function trySubmit() {
		await uploads.wait();
		setSubmitError(null); if (queueRef.current && !await queueRef.current.flush())
			return; const errors = checkComplete(data.definition, valuesRef.current); if (errors.length) {
				showErrors(errors);
				return;
			} setConfirmOpen(true);
	}
	async function submit() {
		await uploads.wait();
		setSubmitting(true); setSubmitError(null); try {
			if (queueRef.current && !await queueRef.current.flush()) {
				setConfirmOpen(false);
				return;
			}
			const errors = checkComplete(data.definition, valuesRef.current);
			if (errors.length) {
				setConfirmOpen(false);
				showErrors(errors);
				return;
			}
			await post("forms_core.api.submit", { name: data.name });
			setConfirmOpen(false);
			await reload();
			window.scrollTo({ top: 0 });
		}
		catch (e) {
			if (e instanceof ApiError && e.formErrors) {
				setConfirmOpen(false);
				showErrors(e.formErrors);
			}
			else
				setSubmitError(e instanceof Error ? e.message : String(e));
		}
		finally {
			setSubmitting(false);
		}
	}
	const header = screenHeader(data.context_values), done = progress(data.definition, values), mapped = errorsByField(data.definition, problems, values), documents = toDocuments(data.references, data.definition);
	const back = data.context_doctype === "DeployOps Job" && data.context_name ? `/job/${encodeURIComponent(data.context_name)}` : !data.context_doctype ? `/f/${encodeURIComponent(data.form)}` : "/";
	return <><TopBar title={data.title} subtitle={`${data.name}${header.customer ? ` · ${header.customer}` : ""}`} back={back} right={editable ? <span className="text-sm text-muted">{saveState === "saving" ? "Saving…" : saveState === "saved" ? "Saved" : saveState === "offline" ? "Offline" : ""}</span> : undefined} progress={editable ? done : undefined} />
		<Page className={editable ? "pb-36" : "pb-24"}><header><p className="font-mono text-xs text-muted">{data.name} · Form v{data.version_no}</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">{data.title}</h1><dl className="mt-6 grid grid-cols-2 gap-4">{Object.entries(header).map(([key, value]) => <div key={key}><dt className="text-xs capitalize text-muted">{key}</dt><dd className="font-medium">{value ?? "—"}</dd></div>)}</dl></header><div className="mt-6 space-y-3">{data.docstatus === 1 && <Banner kind="success">Submitted on {data.submitted_on ? new Date(data.submitted_on.replace(" ", "T")).toLocaleString("en-GB") : "—"} by {data.submitted_by ?? "—"}. This form is locked.</Banner>}{data.docstatus === 1 && !bare && <div className="flex flex-wrap gap-2"><a href={pdfUrl(data.name, "internal")} className="inline-flex h-11 items-center gap-2 rounded-full bg-zinc-100 px-5 text-sm font-medium hover:bg-zinc-200"><FileDown className="size-4" />Download PDF</a><a href={pdfUrl(data.name, "customer")} className="inline-flex h-11 items-center gap-2 rounded-full bg-zinc-100 px-5 text-sm font-medium hover:bg-zinc-200"><FileDown className="size-4" />Customer copy</a></div>}{data.docstatus === 1 && !data.context_doctype && <Link to={`/f/${encodeURIComponent(data.form)}`} className="inline-flex h-11 items-center gap-2 rounded-full bg-brand-500 px-5 text-sm font-medium text-white hover:bg-brand-600"><Plus className="size-4" />Fill in another entry</Link>}{data.docstatus === 2 && <Banner kind="warning">This form was cancelled.</Banner>}{data.amended_from && <Banner kind="warning">This form amends {data.amended_from}.</Banner>}{saveState === "offline" && <Banner kind="warning">You're offline. Changes are kept on this page and saved when you're back online.</Banner>}{saveState === "error" && saveError && <Banner>{saveError.message}</Banner>}{mapped.byField.size > 0 && <Banner>{mapped.byField.size} answers still needed.</Banner>}{mapped.general.map((message, i) => <Banner key={i}>{message}</Banner>)}</div>
			<FormRenderer definition={data.definition} answers={values} errors={mapped.byField} references={data.references} ctx={{ mode: editable ? "fill" : "readonly", values: data.context_values, ...(editable ? { upload: (file: Blob, filename: string) => uploads.run(() => uploadPrivateFile(file, filename, "Form Submission", data.name)) } : {}) }} onChange={change} /></Page>
		<DocumentsDock {...documents} raised={editable} />{data.can_submit && data.docstatus === 0 && <footer className="fixed bottom-0 left-(--shell-left) right-0 z-30 bg-white px-5 py-4"><div className="mx-auto flex max-w-[52rem] items-center gap-3"><span className="text-sm text-muted">{Math.round(done * 100)}%</span><Button className="flex-1" disabled={uploadCount > 0 || submitting} onClick={() => void trySubmit()}>Submit form</Button></div></footer>}
		<ActionDialog open={confirmOpen} title="Submit form?" needsReason={false} warning="The answers are locked once submitted." confirmLabel="Submit form" busy={submitting} error={submitError} onConfirm={() => void submit()} onClose={() => setConfirmOpen(false)} /></>;
}
