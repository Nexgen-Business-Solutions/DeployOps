import { ArrowUpRight, Check, ChevronRight, Phone } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { ActionButtons } from "../components/Actions";
import { Banner, Button, Page, Skeleton, Status, TopBar } from "../components/ui";
import { ApiError, plainText, post } from "../lib/api";
import { formPath } from "../lib/form";
import { formatDate } from "../lib/format";
import type { JobView, Machine } from "../lib/types";
import { useApi } from "../lib/useApi";

function phoneNumbers(contact: string | null): string[] {
	return (contact ?? "").split("\n").filter((line) => /^\+?[\d\s()-]{6,}$/.test(line.trim()));
}

export default function Job() {
	const { job = "" } = useParams();
	const { data, error, loading, reload } = useApi<JobView>("deployops.api.technician.job_view", { job });
	const address = data?.address ? plainText(data.address) : "";

	return (
		<>
			<TopBar back="/" title={data?.name} />
			<Page>
				{error && <Banner>{error.message}</Banner>}
				{loading && !data && <Skeleton className="h-64" />}
				{data && (
					<>
						<div className="flex items-center justify-between">
							<p className="eyebrow">{data.job_type}</p>
							<Status status={data.status} />
						</div>
						<h2 className="mt-2 text-[28px] font-semibold leading-tight tracking-tight">{data.customer_name}</h2>

						<dl className="mt-6 divide-y divide-line border-y border-line text-[15px]">
							<Row label="Planned">{formatDate(data.planned_date)}</Row>
							{address && (
								<Row label="Site">
									<a
										className="inline-flex items-start gap-1 whitespace-pre-line hover:text-brand-500"
										href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address.replace(/\n/g, ", "))}`}
										target="_blank"
										rel="noreferrer"
									>
										{address}
										<ArrowUpRight className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
									</a>
								</Row>
							)}
							{data.contact && (
								<Row label="Contact">
									<p className="whitespace-pre-line">{data.contact}</p>
									{phoneNumbers(data.contact).map((phone) => (
										<a
											key={phone}
											href={`tel:${phone.replace(/\s/g, "")}`}
											className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-zinc-100 px-3 py-1.5 text-sm font-medium hover:bg-zinc-200"
										>
											<Phone className="size-3.5" aria-hidden /> Call
										</a>
									))}
								</Row>
							)}
							<Row label="Source">{data.source}</Row>
						</dl>

						{data.actions.length > 0 && (
							<div className="mt-6">
								<ActionButtons actions={data.actions} method="deployops.api.jobs.job_action" args={{ job: data.name }} onDone={reload} />
							</div>
						)}

						<p className="eyebrow mt-12">Machines</p>
						<ul className="mt-2 divide-y divide-line border-y border-line">
							{data.machines.map((machine) => (
								<MachineRow key={machine.row} job={data.name} machine={machine} onChange={reload} />
							))}
						</ul>
					</>
				)}
			</Page>
		</>
	);
}

function Row({ label, children }: { label: string; children: ReactNode }) {
	return (
		<div className="flex gap-4 py-3.5">
			<dt className="w-20 shrink-0 text-muted">{label}</dt>
			<dd className="min-w-0 flex-1">{children}</dd>
		</div>
	);
}

function MachineRow({ job, machine, onChange }: { job: string; machine: Machine; onChange: () => void }) {
	const navigate = useNavigate();
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const form = machine.checklist;

	async function start() {
		setBusy(true);
		setError(null);
		try {
			const created = await post<{ doctype: string; name: string }>("deployops.api.checklists.start_checklist", { job, device: machine.row });
			navigate(formPath(created.doctype, created.name));
		} catch (e) {
			setError(e instanceof ApiError ? e.message : String(e));
			setBusy(false);
		}
	}

	return (
		<li className="py-4">
			<div className="flex items-start justify-between gap-3">
				<div className="min-w-0">
					<p className="truncate font-medium">{machine.item_name || machine.item_code}</p>
					<p className="truncate font-mono text-[13px] text-muted">{machine.serial_no ?? "Serial not picked yet"}</p>
				</div>
				<Status status={machine.status} />
			</div>

			{form ? (
				<Link
					to={formPath(form.doctype, form.name)}
					className="group mt-3 flex items-center gap-3 rounded-2xl bg-zinc-50 px-4 py-3 hover:bg-zinc-100"
				>
					<span className={`grid size-6 place-items-center rounded-full ${form.submitted ? "bg-emerald-500 text-white" : "border-2 border-dashed border-zinc-300"}`}>
						{form.submitted && <Check className="size-3.5" strokeWidth={3} />}
					</span>
					<span className="flex-1 text-[15px]">{form.submitted ? "Checklist submitted" : "Continue checklist"}</span>
					<ChevronRight className="size-[18px] text-zinc-300 group-hover:text-ink" />
				</Link>
			) : (
				machine.can_start_checklist && (
					<Button className="mt-3 h-11 w-full" loading={busy} onClick={() => void start()}>
						Start checklist
					</Button>
				)
			)}

			{machine.actions.length > 0 && (
				<div className="mt-3">
					<ActionButtons actions={machine.actions} method="deployops.api.jobs.device_action" args={{ job, device: machine.row }} onDone={onChange} size="sm" />
				</div>
			)}
			{error && (
				<div className="mt-3">
					<Banner>{error}</Banner>
				</div>
			)}
		</li>
	);
}
