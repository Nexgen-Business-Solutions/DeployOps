// Job checklist rules: which job types and equipment get this form (DeployOps Form Rules).
import { Briefcase, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { post } from "../lib/api";
import { useApi } from "../lib/useApi";
import { Alert, Badge, Btn, ChoiceCards, Confirm, IconBtn, Modal, Spinner } from "./kit";

type Rule = {name: string; job_type: string; equipment_category: string; required: number; active: number; open_jobs: number};
type Rules = {rules: Rule[]; job_types: string[]; categories: string[]};
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function Rules({form, published}: {form: string; published: boolean}) {
	const {data, error, reload} = useApi<Rules>("deployops.api.forms.form_rules", {form});
	const [editing, setEditing] = useState<Partial<Rule> | null>(null), [removing, setRemoving] = useState<Rule>();
	const [busy, setBusy] = useState(false), [notice, setNotice] = useState("");
	async function toggle(rule: Rule) {
		setNotice("");
		try {await post("deployops.api.forms.save_form_rule", {form, ...rule, active: rule.active ? 0 : 1}); await reload();}
		catch (e) {setNotice(message(e));}
	}
	async function remove(rule: Rule) {
		setBusy(true);
		try {await post("deployops.api.forms.delete_form_rule", {name: rule.name}); setRemoving(undefined); await reload();}
		catch (e) {setNotice(message(e)); setRemoving(undefined);} finally {setBusy(false);}
	}
	return <div className="space-y-4">
		<div className="flex items-end gap-3">
			<div className="flex-1"><h2 className="text-lg font-semibold text-slate-900">Jobs that use this checklist</h2>
				<p className="mt-1 text-sm text-slate-500">A rule adds this checklist to every machine of an equipment category on jobs of one type. Open jobs are updated straight away; machines that already have an entry keep theirs.</p></div>
			<Btn tone="primary" icon={<Plus className="size-4" />} disabled={!data} onClick={() => setEditing({required: 1, active: 1})}>Add rule</Btn>
		</div>
		{!published && <Alert kind="info">Publish the form first. A rule can only switch on a published form.</Alert>}
		{(error || notice) && <Alert>{notice || error?.message}</Alert>}
		<div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200">
			{!data ? <Spinner label="Loading rules" /> : data.rules.length === 0 ? <div className="flex flex-col items-center px-6 py-14 text-center">
				<span className="grid size-12 place-items-center rounded-xl bg-violet-50 text-violet-600"><Briefcase className="size-6" /></span>
				<p className="mt-4 font-semibold text-slate-900">No jobs get this checklist yet</p>
				<p className="mt-1 max-w-sm text-sm text-slate-500">Add a rule, for example "Pre-installation jobs, Cashmatic machines".</p>
			</div> : <table className="w-full text-left text-sm">
				<thead className="border-b border-slate-200 bg-slate-50/80 text-xs font-medium uppercase tracking-wide text-slate-500"><tr>
					<th className="py-3 pl-5 pr-3">Job type</th><th className="px-3 py-3">Equipment</th><th className="px-3 py-3">Checklist is</th><th className="px-3 py-3">Open jobs</th><th className="px-3 py-3">Status</th><th className="py-3 pl-3 pr-5" />
				</tr></thead>
				<tbody className="divide-y divide-slate-100">{data.rules.map(rule => <tr key={rule.name}>
					<td className="py-3 pl-5 pr-3 font-medium text-slate-900">{rule.job_type}</td>
					<td className="px-3 py-3 text-slate-700">{rule.equipment_category}</td>
					<td className="px-3 py-3 text-slate-700">{rule.required ? "Required" : "Optional"}</td>
					<td className="px-3 py-3 tabular-nums text-slate-600">{rule.active ? rule.open_jobs : "—"}</td>
					<td className="px-3 py-3"><button type="button" role="switch" aria-checked={!!rule.active} aria-label={`${rule.active ? "Turn off" : "Turn on"} ${rule.job_type} / ${rule.equipment_category}`} onClick={() => void toggle(rule)}
						className="inline-flex items-center gap-2 text-sm"><span className={`relative h-5 w-9 rounded-full transition ${rule.active ? "bg-emerald-500" : "bg-slate-300"}`}><span className={`absolute top-0.5 size-4 rounded-full bg-white shadow transition-all ${rule.active ? "left-[18px]" : "left-0.5"}`} /></span><Badge kind={rule.active ? "Published" : "Archived"}>{rule.active ? "On" : "Off"}</Badge></button></td>
					<td className="py-2 pl-3 pr-5"><div className="flex justify-end gap-1">
						<IconBtn label={`Edit ${rule.job_type} / ${rule.equipment_category}`} onClick={() => setEditing(rule)}><Pencil className="size-4" /></IconBtn>
						<IconBtn label={`Remove ${rule.job_type} / ${rule.equipment_category}`} className="hover:!bg-red-50 hover:!text-red-600" onClick={() => setRemoving(rule)}><Trash2 className="size-4" /></IconBtn>
					</div></td>
				</tr>)}</tbody>
			</table>}
		</div>
		{editing && data && <RuleDialog form={form} rule={editing} options={data} onClose={() => setEditing(null)} onSaved={async () => {setEditing(null); await reload();}} />}
		<Confirm open={!!removing} danger busy={busy} title="Remove this rule?" confirmLabel="Remove rule" onClose={() => setRemoving(undefined)} onConfirm={() => void remove(removing!)}
			message={<>{removing?.job_type} jobs with {removing?.equipment_category} machines stop getting this checklist. Machines that already started it keep their entry.</>} />
	</div>;
}

function RuleDialog({form, rule, options, onClose, onSaved}: {form: string; rule: Partial<Rule>; options: Rules; onClose: () => void; onSaved: () => Promise<void>}) {
	const [jobType, setJobType] = useState(rule.job_type ?? ""), [category, setCategory] = useState(rule.equipment_category ?? "");
	const [required, setRequired] = useState<"1" | "0">(rule.required === 0 ? "0" : "1");
	const [busy, setBusy] = useState(false), [error, setError] = useState("");
	async function save() {
		if (!jobType || !category) {setError("Choose a job type and an equipment category."); return;}
		setBusy(true); setError("");
		try {await post("deployops.api.forms.save_form_rule", {form, name: rule.name, job_type: jobType, equipment_category: category, required: Number(required), active: rule.active ?? 1}); await onSaved();}
		catch (e) {setError(message(e));} finally {setBusy(false);}
	}
	const select = (label: string, value: string, set: (v: string) => void, list: string[], placeholder: string) => <label className="block"><span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
		<select className="bld-input" value={value} onChange={e => set(e.target.value)}><option value="" disabled>{placeholder}</option>{list.map(o => <option key={o} value={o}>{o}</option>)}</select></label>;
	return <Modal open title={rule.name ? "Edit rule" : "Add a rule"} description="Machines of this equipment on jobs of this type get the checklist." onClose={onClose}
		footer={<><Btn onClick={onClose}>Cancel</Btn><Btn tone="primary" loading={busy} onClick={() => void save()}>{rule.name ? "Save rule" : "Add rule"}</Btn></>}>
		<div className="space-y-5">
			<div className="grid gap-4 sm:grid-cols-2">
				{select("Job type", jobType, setJobType, options.job_types, "Choose a job type")}
				{select("Equipment", category, setCategory, options.categories, "Choose equipment")}
			</div>
			<div><span className="mb-2 block text-sm font-medium text-slate-700">The checklist is</span>
				<ChoiceCards value={required} onChange={setRequired} options={[
					{value: "1", title: "Required", text: "The machine can't be completed until it's submitted.", icon: <span className="text-sm font-bold">!</span>},
					{value: "0", title: "Optional", text: "Technicians can fill it, or a supervisor can remove it.", icon: <span className="text-sm font-bold">?</span>},
				]} /></div>
			{error && <Alert>{error}</Alert>}
		</div>
	</Modal>;
}
