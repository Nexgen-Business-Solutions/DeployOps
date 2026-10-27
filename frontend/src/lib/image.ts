/** Shrink a photo on the phone before upload (longest side 1600 px, JPEG), keeping uploads fast. */
export async function resizeImage(file: File, maxSide = 1600, quality = 0.85): Promise<Blob> {
	if (!file.type.startsWith("image/") || file.type === "image/gif") return file;
	const url = URL.createObjectURL(file);
	try {
		const image = await new Promise<HTMLImageElement>((resolve, reject) => {
			const img = new Image();
			img.onload = () => resolve(img);
			img.onerror = reject;
			img.src = url;
		});
		const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
		const canvas = document.createElement("canvas");
		canvas.width = Math.round(image.naturalWidth * scale);
		canvas.height = Math.round(image.naturalHeight * scale);
		const context = canvas.getContext("2d");
		if (!context) return file;
		context.drawImage(image, 0, 0, canvas.width, canvas.height);
		const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
		return blob ?? file;
	} catch {
		return file;
	} finally {
		URL.revokeObjectURL(url);
	}
}
