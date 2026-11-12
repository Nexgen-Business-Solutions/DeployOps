import { newId } from "./ids";
import type { Definition } from "../forms/types";
export async function duplicateForm(data: unknown, send: (args: Record<string, unknown>) => Promise<unknown>) {
	return send({data, key: `form-${newId("f").slice(2)}-${newId("f").slice(2)}`});
}
export function replaceReference(current: NonNullable<Definition["references"]>, added: NonNullable<Definition["references"]>[number]) {return [...current, added];}
export const conditionDepthAllowed = (depth: number) => depth < 3;
export async function beforeRestore(flush: () => Promise<void>, token: () => string, restore: (modified: string) => Promise<unknown>, reload: () => Promise<unknown>) {await flush(); await restore(token()); await reload();}
export async function publishChecked(flush: () => Promise<void>, check: () => Promise<{errors: unknown[]; modified: string}>, publish: (modified: string) => Promise<unknown>) {
	await flush(); const result = await check(); if (result.errors.length) throw new Error("The draft has validation errors. Close and reopen Publish to review them."); await publish(result.modified);
}
export async function saveBeforeNavigation(flush: () => Promise<void>, proceed: () => void, stay: (message: string) => void) {
	try {await flush(); proceed();} catch(e) {stay(e instanceof Error ? e.message : String(e));}
}
export function errorTarget(definition: Definition, id: string): string {
	for (const section of definition.sections)
		for (const field of section.fields)
			if (((field.config?.columns ?? []) as {id: string}[]).some(column => column.id === id)) return field.id;
	return id;
}
