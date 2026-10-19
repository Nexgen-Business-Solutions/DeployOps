import { ChevronRight } from "lucide-react";
import { Link, useParams } from "react-router";

import { Banner, Empty, Page, Skeleton, Status, TopBar } from "../components/ui";
import { formatDate, firstLine } from "../lib/format";
import type { Card, JobRow } from "../lib/types";
import { useApi } from "../lib/useApi";

export default function CardJobs() {
	const { card = "" } = useParams();
	const { data, error, loading } = useApi<{ card: Card; jobs: JobRow[] }>("deployops.api.technician.my_jobs", { card });

	return (
		<>
			<TopBar back="/" />
			<Page>
				<p className="eyebrow">{data?.card.subtitle ?? " "}</p>
				<h2 className="mt-2 text-[28px] font-semibold leading-tight tracking-tight">{data?.card.title ?? "My jobs"}</h2>

				{error && (
					<div className="mt-6">
						<Banner>{error.message}</Banner>
					</div>
				)}
				{loading && !data && <Skeleton className="mt-8 h-40" />}
				{data && data.jobs.length === 0 && <Empty title="Nothing to do here" text="Jobs assigned to you for this checklist appear here." />}

				{data && data.jobs.length > 0 && (
					<ul className="mt-8 divide-y divide-line border-y border-line">
						{data.jobs.map((job) => (
							<li key={job.name}>
								<Link to={`/job/${encodeURIComponent(job.name)}`} className="group -mx-3 flex items-center gap-4 rounded-2xl px-3 py-4 hover:bg-zinc-50">
									<span className="w-12 shrink-0 text-center">
										<span className="block text-[11px] font-medium uppercase text-muted">
											{job.planned_date ? formatDate(job.planned_date).split(" ")[0] : "—"}
										</span>
										<span className="block text-xl font-semibold tabular-nums leading-tight">
											{job.planned_date ? Number(job.planned_date.slice(8, 10)) : ""}
										</span>
									</span>
									<span className="min-w-0 flex-1">
										<span className="block truncate font-medium">{job.customer_name || job.name}</span>
										<span className="block truncate text-sm text-muted">{firstLine(job.address_display) || "No site address"}</span>
										<span className="mt-1 flex items-center gap-3">
											<Status status={job.status} />
											<span className="text-[13px] text-muted">
												{job.machines} machine{job.machines === 1 ? "" : "s"}
											</span>
										</span>
									</span>
									<ChevronRight className="size-[18px] text-zinc-300 group-hover:text-ink" />
								</Link>
							</li>
						))}
					</ul>
				)}
			</Page>
		</>
	);
}
