import fs from 'fs';
import type { IncomingMessage } from 'http';
import path from 'path';

const common_site_config = JSON.parse(
	fs.readFileSync(path.resolve(__dirname, '../../../sites/common_site_config.json'), 'utf-8')
);
const { webserver_port } = common_site_config;

export default {
	'^/(app|api|assets|files|private)': {
		target: `http://127.0.0.1:${webserver_port}`,
		ws: true,
		router: function(req: IncomingMessage) {
			const site_name = (req.headers.host ?? '').split(':')[0];
			return `http://${site_name}:${webserver_port}`;
		}
	}
};
