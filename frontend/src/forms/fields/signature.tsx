import { useState } from "react";
import { SignaturePad } from "../../components/form/SignaturePad";
import { dataUrlToBlob } from "../../lib/image";
import type { FieldInputProps } from "./index";
export function SignatureInput({ field, value, disabled, ctx, onChange }: FieldInputProps) {
	const answer = value as {
		file: string;
		signer?: string;
		signed_at?: string;
	} | null;
	const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
	async function capture(url: string | null) {
		if (!url) {
			onChange(null);
			return;
		} setBusy(true); setError(null); try {
			onChange({ file: ctx.upload ? await ctx.upload(dataUrlToBlob(url), `signature-${field.id}.png`) : url });
		}
		catch (e) {
			setError(e instanceof Error ? e.message : "Signature could not be uploaded.");
		}
		finally {
			setBusy(false);
		}
	}
	return <div><SignaturePad value={answer?.file ?? null} disabled={disabled || busy} onChange={url => void capture(url)} />{busy && <p className="text-sm text-muted">Uploading…</p>}{answer?.signer && <p className="mt-2 text-sm text-muted">Signed by {answer.signer}{answer.signed_at ? ` · ${new Date(answer.signed_at.replace(" ", "T")).toLocaleString("en-GB")}` : ""}</p>}{error && <p role="alert" className="text-red-600">{error}</p>}</div>;
}
