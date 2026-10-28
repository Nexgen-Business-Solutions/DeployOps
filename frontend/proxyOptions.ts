import fs from 'fs';
import type { IncomingMessage } from 'http';
import path from 'path';

/**
 * Dev-server proxy to the bench web server. Called only by `vite` (serve), never by builds or
 * tests, so those work outside a bench (e.g. in CI) where sites/common_site_config.json is absent.
 */
export default function devProxy() {
	const configPath = path.resolve(__dirname, '../../../sites/common_site_config.json');
	if (!fs.existsSync(configPath)) return undefined;
	const { webserver_port } = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
	return {
		'^/(app|api|assets|files|private)': {
			target: `http://127.0.0.1:${webserver_port}`,
			ws: true,
			router: function (req: IncomingMessage) {
				const site_name = (req.headers.host ?? '').split(':')[0];
				return `http://${site_name}:${webserver_port}`;
			},
		},
	};
}
