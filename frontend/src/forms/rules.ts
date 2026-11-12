// Source: forms_core/js/src/rules.ts
// Keep the following source verbatim; rules.parity.test.ts detects drift.
// TypeScript twin of forms_core/rules.py. Both are proven by forms_core/rules_cases.json.

export type Op = "eq" | "ne" | "in" | "not_in" | "gt" | "gte" | "lt" | "lte" | "empty" | "not_empty" | "contains";

export type Condition = { field: string; op: Op; value?: unknown };
export type Rule = Condition | { all: Rule[] } | { any: Rule[] } | { not: Rule };
export type Answers = Record<string, unknown>;

const isNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

const isObject = (v: unknown): v is Record<string, unknown> =>
	typeof v === "object" && v !== null && !Array.isArray(v);

function isEmpty(v: unknown): boolean {
	if (v === null || v === undefined || v === "") return true;
	if (Array.isArray(v)) return v.length === 0;
	if (isObject(v) && "selected" in v) {
		const sel = v.selected;
		const noSelection = sel === null || sel === undefined || (Array.isArray(sel) && sel.length === 0);
		return noSelection && !v.other;
	}
	return false;
}

function equal(a: unknown, b: unknown): boolean {
	if (a === undefined) a = null;
	if (b === undefined) b = null;
	if (Array.isArray(a) && Array.isArray(b)) {
		return a.length === b.length && a.every((x, i) => equal(x, b[i]));
	}
	if (isObject(a) && isObject(b)) {
		const ka = Object.keys(a);
		const kb = Object.keys(b);
		return ka.length === kb.length && ka.every((k) => k in b && equal(a[k], b[k]));
	}
	if (Array.isArray(a) || Array.isArray(b) || isObject(a) || isObject(b)) return false;
	return a === b;
}

function compare(op: Op, answer: unknown, value: unknown): boolean {
	if (!isNumber(answer) || !isNumber(value)) return false;
	if (op === "gt") return answer > value;
	if (op === "gte") return answer >= value;
	if (op === "lt") return answer < value;
	return answer <= value;
}

function contains(answer: unknown, value: unknown): boolean {
	const list = isObject(answer) ? answer.selected : answer;
	return Array.isArray(list) && list.some((item) => equal(item, value));
}

function condition(rule: Condition, answers: Answers): boolean {
	const answer = answers[rule.field] ?? null;
	const value = rule.value;
	switch (rule.op) {
		case "eq":
			return equal(answer, value);
		case "ne":
			return !equal(answer, value);
		case "in":
			return (value as unknown[]).some((v) => equal(answer, v));
		case "not_in":
			return !(value as unknown[]).some((v) => equal(answer, v));
		case "gt":
		case "gte":
		case "lt":
		case "lte":
			return compare(rule.op, answer, value);
		case "empty":
			return isEmpty(answer);
		case "not_empty":
			return !isEmpty(answer);
		case "contains":
			return contains(answer, value);
		default:
			throw new Error(`Unknown op: ${String((rule as { op: unknown }).op)}`);
	}
}

export function evaluate(rule: Rule | null, answers: Answers): boolean {
	if (rule === null) return true;
	if ("all" in rule) return rule.all.every((r) => evaluate(r, answers));
	if ("any" in rule) return rule.any.some((r) => evaluate(r, answers));
	if ("not" in rule) return !evaluate(rule.not, answers);
	return condition(rule, answers);
}

export function references(rule: Rule): Set<string> {
	const out = new Set<string>();
	const walk = (r: Rule): void => {
		if ("all" in r) r.all.forEach(walk);
		else if ("any" in r) r.any.forEach(walk);
		else if ("not" in r) walk(r.not);
		else out.add(r.field);
	};
	walk(rule);
	return out;
}
