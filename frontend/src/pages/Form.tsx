import { BookOpen, Check, CloudOff, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router";

import { FieldInput } from "../components/form/FieldInput";
import { ReferenceCard } from "../components/form/ReferenceCard";
import { ActionDialog, Banner, Button, Page, Skeleton, TopBar } from "../components/ui";
import { ApiError, post } from "../lib/api";
import { findProblems, progress, visibleSections } from "../lib/form";
import type { Field, FormView, Reference, Section, Value, Values } from "../lib/types";
import { useApi } from "../lib/useApi";

type SaveState = "idle" | "saving" | "saved" | "offline" | "error";
const AUTOSAVE_MS = 800;

export default function Form() {
	const { doctype = "", name = "" } = useParams();
	const { data, error, loading, reload } = useApi<FormView>("deployops.api.technician.form_view", { doctype, name });

	const [values, setValues] = useState<Values>({});
	const [problems, setProblems] = useState<Map<string, string>>(new Map());
	const [saveState, setSaveState] = useState<SaveState>("idle");
	const [saveError, setSaveError] = useState<string | null>(null);
	const [confirmOpen, setConfirmOpen] = useState(false);
	const [submitting, setSubmitting] = useState(false);
	const [submitError, setSubmitError] = useState<string | null>(null);

	const pending = useRef<Values>({});
	const timer = useRef<number | undefined>(undefined);
	const [loaded, setLoaded] = useState<FormView | null>(null);

	// Take the server's values whenever a (re)load arrives.
	if (data && loaded !== data) {
		setLoaded(data);
		setValues(data.values);
	}

	const editable = Boolean(data?.can_edit);

	/** Send every pending change in one call; keeps them queued if the network is down. */
	const flush = useCallback(async (): Promise<boolean> => {
		window.clearTimeout(timer.current);
		const batch = pending.current;
		if (!Object.keys(batch).length) return true;
		pending.current = {};
		setSaveState("saving");
		try {
			const result = await post<{ values: Values }>("deployops.api.technician.save_form", { doctype, name, values: batch });
			// Tables come back with their saved rows; keep anything typed since.
			setValues((current) => {
				const next = { ...current };
				for (const key of Object.keys(batch)) {
					if (Array.isArray(result.values[key]) && !(key in pending.current)) next[key] = result.values[key];
				}
				return next;
			});
			setSaveState("saved");
			setSaveError(null);
			return true;
		} catch (e) {
			pending.current = { ...batch, ...pending.current };
			setSaveState(e instanceof ApiError && e.status === 0 ? "offline" : "error");
			setSaveError(e instanceof ApiError ? e.message : String(e));
			return false;
		}
	}, [doctype, name]);

	useEffect(() => {
		const retry = () => void flush();
		window.addEventListener("online", retry);
		return () => window.removeEventListener("online", retry);
	}, [flush]);

	function change(fieldname: string, value: Value) {
		setValues((current) => ({ ...current, [fieldname]: value }));
		pending.current = { ...pending.current, [fieldname]: value };
		setProblems((current) => {
			if (!current.size) return current;
			const next = new Map(current);
			next.delete(fieldname);
			const section = data?.sections.find((s) => s.fields.some((f) => f.fieldname === fieldname));
			if (section) next.delete(section.name);
			return next;
		});
		window.clearTimeout(timer.current);
		timer.current = window.setTimeout(() => void flush(), AUTOSAVE_MS);
	}

	async function trySubmit() {
		if (!data) return;
		setSubmitError(null);
		if (!data.header.serial_no) {
			window.scrollTo({ top: 0, behavior: "smooth" });
			return; // the banner at the top explains: the serial is assigned on the job first (#22)
		}
		const found = findProblems(data.sections, values);
		setProblems(found);
		if (found.size) {
			const first = [...found.keys()][0];
			(document.getElementById(`f-${first}`) ?? document.getElementById(`s-${first}`))?.scrollIntoView({ behavior: "smooth", block: "start" });
			return;
		}
		if (await flush()) setConfirmOpen(true);
	}

	async function submit() {
		setSubmitting(true);
		setSubmitError(null);
		try {
			await post("deployops.api.technician.submit_form", { doctype, name });
			setConfirmOpen(false);
			await reload();
			window.scrollTo({ top: 0, behavior: "smooth" });
		} catch (e) {
			setSubmitError(e instanceof ApiError ? e.message : String(e));
		} finally {
			setSubmitting(false);
		}
	}

	const sections = data ? visibleSections(data.sections, values) : [];
	const done = data ? progress(data.sections, values) : 0;
	const header = data?.header ?? {};

	return (
		<>
			<TopBar title={data?.title} back={data ? `/job/${encodeURIComponent(data.job)}` : "/"} right={editable && <SaveIndicator state={saveState} />} />
			{editable && (
				<div className="sticky top-14 z-10 h-0.5 bg-zinc-100" role="progressbar" aria-valuenow={Math.round(done * 100)} aria-valuemin={0} aria-valuemax={100}>
					<div className="h-full bg-brand-500 transition-[width] duration-500" style={{ width: `${done * 100}%` }} />
				</div>
			)}

			<Page className={editable ? "pb-36" : ""}>
				{error && <Banner>{error.message}</Banner>}
				{loading && !data && <Skeleton className="h-96" />}
				{data && (
					<>
						<p className="eyebrow">
							{data.name}
							{data.form_version ? ` · Form v${data.form_version}` : ""}
						</p>
						<h2 className="mt-2 text-[28px] font-semibold leading-tight tracking-tight">{data.title}</h2>
						<p className="mt-2 text-muted">{data.intro}</p>
						<DocumentsSummary references={data.references} sections={data.sections} />

						<dl className="mt-6 grid grid-cols-2 gap-x-4 gap-y-3 rounded-2xl bg-zinc-50 p-4 text-sm">
							<Meta label="Customer" value={header.customer_name} />
							<Meta label="Machine" value={header.item_name || header.item_code} />
							<Meta label="Serial" value={header.serial_no} mono />
							<Meta label="Technician" value={data.technician_name} />
						</dl>

						<div className="mt-4 space-y-3">
							{data.docstatus === 1 && (
								<Banner kind="success">
									Submitted{data.submitted_on ? ` on ${new Date(data.submitted_on.replace(" ", "T")).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}` : ""}
									{data.submitted_by ? ` by ${data.submitted_by}` : ""}. This checklist is locked.
								</Banner>
							)}
							{data.docstatus === 2 && <Banner kind="warning">This checklist was cancelled.</Banner>}
							{editable && !data.header.serial_no && (
								<Banner kind="warning">
									No serial number yet. Pick the machine's serial on the job before submitting this checklist.
								</Banner>
							)}
							{saveState === "offline" && <Banner kind="warning">You're offline. Changes are kept on this page and saved when you're back online.</Banner>}
							{saveState === "error" && saveError && <Banner>{saveError}</Banner>}
							{problems.size > 0 && (
								<Banner>
									{problems.size} answer{problems.size === 1 ? "" : "s"} still needed.
								</Banner>
							)}
						</div>

						{sections.map((section, index) => (
							<section key={section.name} id={`s-${section.name}`} className="scroll-mt-28 border-t border-line pt-8 mt-10 first-of-type:mt-8">
								{section.label && (
									<header className="mb-5">
										<p className="font-mono text-xs text-zinc-400">{String(index + 1).padStart(2, "0")}</p>
										<h3 className="mt-1 text-xl font-semibold tracking-tight">{section.label}</h3>
										{section.description && <p className="mt-1 text-sm text-muted">{section.description}</p>}
										<SectionReferences items={data.references.filter((r) => r.section === section.name)} />
										{section.any_of && editable && (
											<p className={`mt-1 text-[13px] ${problems.has(section.name) ? "text-red-600" : "text-muted"}`}>Tick at least one.</p>
										)}
									</header>
								)}
								<div className="space-y-6">
									{groupSteps(section.fields).map((group) => (
										<div key={group[0].fieldname}>
											{group.map((field) => (
												<FieldInput
													key={field.fieldname}
													field={field}
													value={values[field.fieldname]}
													error={problems.get(field.fieldname)}
													disabled={!editable}
													doctype={data.doctype}
													docname={data.name}
													signedBy={data.signatures?.[field.fieldname]}
													onChange={(value) => change(field.fieldname, value)}
												/>
											))}
										</div>
									))}
								</div>
							</section>
						))}
					</>
				)}
			</Page>

			{editable && (
				<footer className="fixed inset-x-0 bottom-0 z-30 bg-gradient-to-t from-white via-white to-white/0 px-5 pb-[max(env(safe-area-inset-bottom),1rem)] pt-8">
					<div className="mx-auto flex max-w-[52rem] items-center gap-3">
						<span className="w-16 text-sm tabular-nums text-muted">{Math.round(done * 100)}%</span>
						<Button className="flex-1" onClick={() => void trySubmit()}>
							Submit checklist
						</Button>
					</div>
				</footer>
			)}

			<ActionDialog
				open={confirmOpen}
				title="Submit checklist?"
				needsReason={false}
				warning="The answers are locked once submitted."
				confirmLabel="Submit"
				busy={submitting}
				error={submitError}
				onConfirm={() => void submit()}
				onClose={() => setConfirmOpen(false)}
			/>
		</>
	);
}

/** Every document of the checklist, once each, near the top, so none is missed. */
function DocumentsSummary({ references, sections }: { references: Reference[]; sections: Section[] }) {
	if (!references.length) return null;
	const labels = new Map(sections.map((s) => [s.name, s.label]));
	const documents = new Map<string, { reference: Reference; places: string[] }>();
	for (const reference of references) {
		const entry = documents.get(reference.url) ?? { reference, places: [] };
		if (reference.section && labels.get(reference.section)) entry.places.push(labels.get(reference.section) as string);
		documents.set(reference.url, entry);
	}
	return (
		<section className="mt-6 rounded-2xl bg-brand-50/70 p-4" aria-label="Documents for this checklist">
			<p className="flex items-center gap-2 text-sm font-semibold text-brand-600">
				<BookOpen className="size-4" aria-hidden /> Documents for this checklist ({documents.size})
			</p>
			<p className="mt-0.5 text-[13px] text-muted">Read them before you start; they are also shown in the steps that need them.</p>
			<div className="mt-3 space-y-2">
				{[...documents.values()].map(({ reference, places }) => (
					<ReferenceCard key={reference.url} reference={reference} note={places.length ? `Used in ${places.join(", ")}` : undefined} />
				))}
			</div>
		</section>
	);
}

/** The documents this section needs, right under its heading. */
function SectionReferences({ items }: { items: Reference[] }) {
	if (!items.length) return null;
	return (
		<div className="mt-3 space-y-2">
			{items.map((item) => (
				<ReferenceCard key={`${item.url}-${item.title}`} reference={item} />
			))}
		</div>
	);
}

/** Consecutive tick boxes form one tight list; every other field stands on its own. */
function groupSteps(fields: Field[]): Field[][] {
	const groups: Field[][] = [];
	for (const field of fields) {
		const last = groups.at(-1);
		if (field.fieldtype === "Check" && last?.[0].fieldtype === "Check") last.push(field);
		else groups.push([field]);
	}
	return groups;
}

function Meta({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
	return (
		<div className="min-w-0">
			<dt className="text-[12px] text-muted">{label}</dt>
			<dd className={`truncate font-medium ${mono ? "font-mono text-[13px]" : ""}`}>{value || "—"}</dd>
		</div>
	);
}

function SaveIndicator({ state }: { state: SaveState }) {
	const base = "inline-flex items-center gap-1.5 pr-2 text-[13px]";
	if (state === "saving")
		return (
			<span className={`${base} text-muted`}>
				<Loader2 className="size-3.5 animate-spin" aria-hidden /> Saving
			</span>
		);
	if (state === "saved")
		return (
			<span className={`${base} text-muted`}>
				<Check className="size-3.5" aria-hidden /> Saved
			</span>
		);
	if (state === "offline")
		return (
			<span className={`${base} text-amber-600`}>
				<CloudOff className="size-3.5" aria-hidden /> Offline
			</span>
		);
	return null;
}
