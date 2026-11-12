/// <reference types="node" />
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, it, expect } from "vitest";
import { evaluate, type Rule } from "./rules";
const source=path.resolve(import.meta.dirname,"../../../../forms_core/js/src/rules.ts");
describe.skipIf(!existsSync(source))("rules parity",()=>{
it("copy matches forms_core",()=>expect(readFileSync(path.resolve(import.meta.dirname,"rules.ts"),"utf8").split("\n").slice(2).join("\n")).toBe(readFileSync(source,"utf8")));
it("shared rule cases pass",()=>{const cases=JSON.parse(readFileSync(path.resolve(path.dirname(source),"../../forms_core/rules_cases.json"),"utf8")) as {rule:Rule;answers:Record<string,unknown>;expected:boolean}[];for(const c of cases) expect(evaluate(c.rule,c.answers)).toBe(c.expected);});
});
