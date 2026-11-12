import { DndContext, DragOverlay, PointerSensor, KeyboardSensor, useSensor, useSensors, useDraggable, useDroppable, closestCenter } from "@dnd-kit/core";
import { SortableContext, useSortable, sortableKeyboardCoordinates, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { ArrowDown, ArrowUp, Copy, Eye, GripVertical, Plus, Search, Trash2, Asterisk } from "lucide-react";
import { useState, type ReactNode, type CSSProperties } from "react";
import type { Definition, FieldDef } from "../forms/types";
import type { Catalog } from "./api";
import type { Action } from "./state";
import { newId } from "./ids";
import { FIELD_GROUPS, FieldIcon, fieldLabel } from "./fieldIcons";
import { IconBtn } from "./kit";

export function Canvas({definition, catalog, selected, select, apply, add, remove}: {definition: Definition; catalog: Catalog; selected: string; select: (id: string) => void; apply: (action: Action) => void; add: (type: string, section?: string, index?: number) => void; remove: (id: string, section: boolean) => void}) {
	const sensors = useSensors(useSensor(PointerSensor, {activationConstraint: {distance: 6}}), useSensor(KeyboardSensor, {coordinateGetter: sortableKeyboardCoordinates}));
	const [dragging, setDragging] = useState<string>();
	const allFields = definition.sections.flatMap(s => s.fields);
	const dragLabel = dragging?.startsWith("palette:") ? fieldLabel(dragging.slice(8)) : allFields.find(f => f.id === dragging)?.label;
	const dragType = dragging?.startsWith("palette:") ? dragging.slice(8) : allFields.find(f => f.id === dragging)?.type;
	return <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={({active}) => setDragging(String(active.id))} onDragCancel={() => setDragging(undefined)} onDragEnd={({active, over}) => {
		setDragging(undefined);
		if (!over || active.id === over.id) return;
		const section = definition.sections.find(s => s.id === over.id || s.fields.some(f => f.id === over.id)); if (!section) return;
		const index = section.fields.findIndex(f => f.id === over.id);
		if (String(active.id).startsWith("palette:")) add(String(active.id).slice(8), section.id, index < 0 ? section.fields.length : index);
		else apply({type: "moveField", id: String(active.id), section: section.id, index: index < 0 ? section.fields.length : index});
	}}>
		<div className="grid min-h-0 flex-1 grid-cols-[15rem_minmax(0,1fr)]">
			<Palette types={catalog.field_types} add={add} />
			<div className="min-h-0 overflow-y-auto bg-slate-100/70 px-8 py-6" onClick={e => {if (e.target === e.currentTarget) select("");}}>
				<div className="mx-auto max-w-2xl space-y-5">
					{definition.sections.map((section, i) => <SectionDrop key={section.id} id={section.id}>
						<section className={`rounded-xl bg-white shadow-sm ring-1 transition ${selected === section.id ? "ring-2 ring-brand-500" : "ring-slate-200"}`}>
							<header className="group flex items-center gap-3 border-b border-slate-100 px-4 py-3">
								<span className="grid size-7 shrink-0 place-items-center rounded-full bg-slate-900 text-xs font-semibold text-white">{i + 1}</span>
								<button type="button" className="min-w-0 flex-1 text-left" onClick={() => select(section.id)}>
									<span className="block truncate font-semibold text-slate-900">{section.title || "Untitled step"}</span>
									<span className="block text-xs text-slate-500">Step {i + 1} of {definition.sections.length} · {section.fields.length} field{section.fields.length === 1 ? "" : "s"}{section.show ? " · conditional" : ""}</span>
								</button>
								<div className="flex items-center opacity-60 transition group-hover:opacity-100">
									<IconBtn label="Move step up" disabled={i === 0} onClick={() => apply({type: "moveSection", id: section.id, index: i - 1})}><ArrowUp className="size-4" /></IconBtn>
									<IconBtn label="Move step down" disabled={i === definition.sections.length - 1} onClick={() => apply({type: "moveSection", id: section.id, index: i + 1})}><ArrowDown className="size-4" /></IconBtn>
									<IconBtn label="Duplicate step" onClick={() => apply({type: "duplicateSection", id: section.id})}><Copy className="size-4" /></IconBtn>
									<IconBtn label="Delete step" className="hover:!bg-red-50 hover:!text-red-600" disabled={definition.sections.length === 1} onClick={() => remove(section.id, true)}><Trash2 className="size-4" /></IconBtn>
								</div>
							</header>
							<div className="space-y-2 p-3">
								<SortableContext items={section.fields.map(f => f.id)} strategy={verticalListSortingStrategy}>{section.fields.map(field => <SortableField key={field.id} field={field} selected={selected === field.id} select={select} duplicate={() => apply({type: "duplicateField", id: field.id})} remove={() => remove(field.id, false)} />)}</SortableContext>
								{!section.fields.length && <p className="rounded-lg border-2 border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500">Drag a field here, or pick one from the left</p>}
							</div>
						</section>
					</SectionDrop>)}
					<button type="button" onClick={() => {const id = newId("s"); apply({type: "addSection", section: {id, title: `Step ${definition.sections.length + 1}`, fields: []}}); select(id);}}
						className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-300 py-4 text-sm font-medium text-slate-600 transition hover:border-brand-500 hover:bg-white hover:text-brand-600"><Plus className="size-4" />Add step</button>
				</div>
			</div>
		</div>
		<DragOverlay dropAnimation={null}>{dragging && <div className="flex w-64 items-center gap-2 rounded-lg bg-white px-3 py-2.5 text-sm font-medium shadow-xl ring-2 ring-brand-500">{dragType && <FieldIcon type={dragType} />}{dragLabel}</div>}</DragOverlay>
	</DndContext>;
}

function Palette({types, add}: {types: Catalog["field_types"]; add: (type: string) => void}) {
	const [query, setQuery] = useState("");
	const offered = new Set(types.map(t => t.type)), listed = new Set(FIELD_GROUPS.flatMap(([, t]) => t));
	const groups: [string, string[]][] = [...FIELD_GROUPS.map(([g, t]) => [g, t.filter(x => offered.has(x))] as [string, string[]]), ["Other", types.map(t => t.type).filter(t => !listed.has(t))]];
	const match = (t: string) => fieldLabel(t, types.find(x => x.type === t)?.label).toLowerCase().includes(query.trim().toLowerCase());
	return <aside className="min-h-0 overflow-y-auto border-r border-slate-200 bg-white px-3 py-4" aria-label="Fields">
		<label className="relative block"><Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-slate-400" /><input className="bld-input py-1.5 pl-8 text-[13px]" placeholder="Find a field" value={query} onChange={e => setQuery(e.target.value)} /></label>
		{groups.map(([group, list]) => {const shown = list.filter(match); return shown.length > 0 && <div key={group} className="mt-4">
			<p className="mb-1.5 px-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-400">{group}</p>
			<div className="space-y-0.5">{shown.map(t => <PaletteItem key={t} type={t} label={fieldLabel(t, types.find(x => x.type === t)?.label)} add={add} />)}</div>
		</div>;})}
		<p className="mt-5 px-1 text-xs leading-relaxed text-slate-400">Click to add after the selected field, or drag onto a step.</p>
	</aside>;
}

function PaletteItem({type, label, add}: {type: string; label: string; add: (type: string) => void}) {
	const {attributes, listeners, setNodeRef} = useDraggable({id: `palette:${type}`});
	return <button ref={setNodeRef} type="button" {...listeners} {...attributes} onClick={() => add(type)} aria-label={`Add ${label}`}
		className="group flex w-full touch-none items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-[13px] font-medium text-slate-700 transition hover:bg-slate-100 hover:text-slate-900">
		<span className="grid size-7 place-items-center rounded-md bg-slate-100 text-slate-600 group-hover:bg-white group-hover:text-brand-600 group-hover:shadow-xs"><FieldIcon type={type} className="size-3.5" /></span>
		<span className="flex-1">{label}</span><Plus className="size-3.5 text-slate-300 opacity-0 group-hover:opacity-100" />
	</button>;
}

function SectionDrop({id, children}: {id: string; children: ReactNode}) {const {setNodeRef} = useDroppable({id}); return <div ref={setNodeRef}>{children}</div>;}

function SortableField({field, selected, select, duplicate, remove}: {field: FieldDef; selected: boolean; select: (id: string) => void; duplicate: () => void; remove: () => void}) {
	const {attributes, listeners, setNodeRef, transform, transition, isDragging} = useSortable({id: field.id});
	const style: CSSProperties = {transform: transform ? `translate3d(${transform.x}px,${transform.y}px,0)` : undefined, transition, opacity: isDragging ? .4 : 1};
	const required = field.required || !!field.required_when;
	return <div ref={setNodeRef} style={style} className={`group relative flex items-center gap-2 rounded-lg px-2 py-2.5 ring-1 transition ${selected ? "bg-brand-50/50 ring-2 ring-brand-500" : "bg-white ring-slate-200 hover:ring-slate-300"}`}>
		<button type="button" {...attributes} {...listeners} aria-label={`Move ${field.label}`} className="grid size-7 shrink-0 cursor-grab touch-none place-items-center rounded text-slate-300 hover:bg-slate-100 hover:text-slate-600 active:cursor-grabbing"><GripVertical className="size-4" /></button>
		<span className={`grid size-8 shrink-0 place-items-center rounded-md ${selected ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-600"}`}><FieldIcon type={field.type} /></span>
		<button type="button" className="min-w-0 flex-1 text-left" onClick={() => select(field.id)}>
			<span className="flex min-w-0 items-center gap-1 text-sm font-medium text-slate-900"><span className="truncate">{field.label || "Untitled field"}</span>{required && <Asterisk className="size-3 shrink-0 text-red-500" aria-label="required" />}</span>
			<span className="flex items-center gap-2 text-xs text-slate-500">{fieldLabel(field.type)}{field.show && <span className="inline-flex items-center gap-0.5 text-violet-600"><Eye className="size-3" />conditional</span>}{field.fill_from && <span className="text-blue-600">prefilled</span>}</span>
		</button>
		<div className={`flex items-center transition ${selected ? "opacity-100" : "opacity-0 group-hover:opacity-100 focus-within:opacity-100"}`}>
			<IconBtn label={`Duplicate ${field.label}`} onClick={duplicate}><Copy className="size-4" /></IconBtn>
			<IconBtn label={`Delete ${field.label}`} className="hover:!bg-red-50 hover:!text-red-600" onClick={remove}><Trash2 className="size-4" /></IconBtn>
		</div>
	</div>;
}
